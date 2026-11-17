#!/usr/bin/env python3
"""
Harvester: Batch 55 - Ancient Tamil Ginger (Inji) Processing, Sukku Lime-Curing & Thirikadugu Pharmacy
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
        "slug": "technology-inji-rhizome-peeling-lime-water-steeping-and-sukku-sun-curing",
        "file": "technology-inji-rhizome-peeling-lime-water-steeping-and-sukku-sun-curing.md",
        "category": "technology",
        "name_en": "Inji Rhizome Peeling, Lime-Water Steeping & Sukku Sun-Curing Technology",
        "name_ta": "இஞ்சிக் கிழங்கு தோல்சீவுதல், சுண்ணாம்பு நீர் ஊறவைத்தல் மற்றும் சுக்கு வெயில் உலர்த்தும் தொழில்நுட்பம்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "kurinji",
        "summary_en": "Traditional post-harvest craft converting fresh Inji (Zingiber officinale) rhizomes into chalk-white Sukku: soaking freshly dug hands overnight, scraping the corky periderm with bamboo splinters, steeping in 2 percent calcium hydroxide (chunnambu) lime-water for 6 hours, then sun-curing on raised palm-leaf platforms for 8 to 10 days until moisture falls from 80 percent to 10 percent and the rhizome rings hollow when tapped.",
        "summary_ta": "புதிதாகத் தோண்டிய இஞ்சிக் கிழங்குகளை இரவு முழுவதும் நீரில் ஊறவைத்து, மூங்கில் சீவலால் மேல்தோலைச் சுரண்டி, இரண்டு விழுக்காடு சுண்ணாம்பு நீரில் ஆறு மணி நேரம் ஊறவைத்து, பனையோலைப் பரண்களில் எட்டு முதல் பத்து நாட்கள் வெயிலில் உலர்த்தி வெண்மையான சுக்காக மாற்றும் பாரம்பரியப் பதப்படுத்தும் முறை.",
        "sources": [
            "Pathitruppathu 30",
            "Siddha Gunapadam: Mooligai Vaguppu",
            "Spices Board of India Post-Harvest Manuals"
        ],
        "content": "# Inji Rhizome Peeling, Lime-Water Steeping & Sukku Sun-Curing Technology\n\nGinger (**Zingiber officinale**, Tamil: **இஞ்சி / Inji**) when fresh, becomes **சுக்கு / Sukku** (dry ginger) when cured. The transformation from a watery, perishable rhizome into a stone-hard, chalk-white, decade-stable drug is one of the oldest pharmaceutical processing chains of the Tamil hill country (*Kurinji* and *Mullai* tracts).\n\n### 1. Harvest Timing (*அறுவடைப் பக்குவம்*)\n- Rhizomes destined for Sukku are lifted 8 to 9 months after planting, when the aerial pseudostems yellow and collapse. Earlier harvests (5 to 6 months) give tender, low-fibre *Inji* for pickles and *murabba*; late harvests give high-oleoresin, high-fibre hands ideal for curing.\n- Hands are dug with a flat iron *koththu* (கொத்து) hoe, shaken of soil, and the fibrous roots snapped off by hand.\n\n### 2. Overnight Soaking & Bamboo-Splinter Peeling (*தோல் சீவுதல்*)\n- Fresh hands are soaked overnight in running channel water to loosen the corky periderm.\n- The outer skin is scraped away using sharpened **bamboo splinters** or split coconut shell edges, never iron knives. Iron blades leave black ferric-tannate stains and cut too deeply into the oleoresin cells that lie directly under the epidermis, where gingerol concentration is highest. Shallow scraping preserves the volatile-oil-rich cortical layer.\n\n### 3. Lime-Water Steeping (*சுண்ணாம்பு நீர் ஊறல்*)\n- Peeled rhizomes are immersed for about 6 hours in **2 percent slaked lime-water**: *chunnambu* (calcium hydroxide, Ca(OH)2) obtained by slaking burnt shell lime or kankar.\n- Chemistry: the alkaline medium (pH about 12) saponifies surface lipids and gently hydrolyses pectin; calcium ions cross-link residual pectic acid into calcium pectate, giving a hard, case-hardened surface that resists fungal (*Aspergillus*, *Penicillium*) and insect (*Lasioderma* cigarette beetle) attack. A thin calcium carbonate film forms as the lime absorbs atmospheric CO2 during drying, producing the characteristic **chalky white bloom** of *velluththa sukku* (வெளுத்த சுக்கு).\n- Some workshops repeat the steep-and-dry cycle two or three times for export-grade bleached Sukku.\n\n### 4. Sun-Curing (*வெயில் உலர்த்தல்*)\n- Steeped rhizomes are spread one layer deep on raised platforms of woven palm-leaf or bamboo matting (*paranai*) to keep them off damp earth, and turned twice daily.\n- Over 8 to 10 days moisture falls from about 80 to 82 percent to 8 to 10 percent, a dry-recovery ratio of roughly 5:1 to 6:1 (fresh to dry). The cured hand is finished when it snaps cleanly and **rings hollow when tapped** against a stone.\n- Moderate sun heat (35 to 45 degrees C) is preferred over smoke kilns: it allows partial gingerol-to-shogaol dehydration while retaining zingiberene-rich volatile oil.\n\n### 5. Grading\n- Sukku is graded by colour (white, bold, unbleached brown), fibre, and freedom from mould. Bold, plump, light-coloured hands from the Western Ghats fetched the premium in temple pharmacies and the Musiris export trade.\n"
    },
    {
        "slug": "technology-thirikadugu-tri-pungent-pulverization-and-inji-lehyam-decoction",
        "file": "technology-thirikadugu-tri-pungent-pulverization-and-inji-lehyam-decoction.md",
        "category": "technology",
        "name_en": "Thirikadugu Tri-Pungent Pulverization & Inji Lehyam Decoction Technology",
        "name_ta": "திரிகடுகு முக்காரப் பொடித்தல் மற்றும் இஞ்சி லேகியம் காய்ச்சும் தொழில்நுட்பம்",
        "era": "Sangam Era to Modern Era",
        "year_start": -200,
        "year_end": 2026,
        "thinai": "marutham",
        "summary_en": "Siddha pharmaceutical technique of compounding Thirikadugu, the equal-part (1:1:1) tri-pungent churnam of Sukku dry ginger, Milagu black pepper and Thippili long pepper, by dry-roasting each in an iron vanali, pounding in stone ural with wooden ulakkai, and sieving through fine muslin (vasthirakayam); plus the slow jaggery-and-ghee reduction of fresh Inji juice into Inji Lehyam electuary tested by the thread-forming paagu stage.",
        "summary_ta": "சுக்கு, மிளகு, திப்பிலி ஆகிய மூன்று காரச் சரக்குகளைச் சம அளவில் இரும்பு வாணலியில் வறுத்து, கல் உரலில் உலக்கையால் இடித்து, மெல்லிய துணியில் வஸ்திரகாயம் செய்து திரிகடுகு சூரணம் தயாரிக்கும் முறையும், இஞ்சிச் சாற்றை வெல்லம் நெய்யுடன் பாகுப் பதம் வரும் வரை காய்ச்சி இஞ்சி லேகியம் செய்யும் சித்த மருந்தாக்க முறையும்.",
        "sources": [
            "Thirikadugam (Nallathanar)",
            "Agathiyar Gunavagadam",
            "Siddha Formulary of India, Part I"
        ],
        "content": "# Thirikadugu Tri-Pungent Pulverization & Inji Lehyam Decoction Technology\n\n**திரிகடுகு / Thirikadugu** (Sanskrit *Trikatu*, \"three pungents\") is the foundational compound of Siddha and Ayurvedic pharmacy: **Sukku** (dry ginger, *Zingiber officinale*), **Milagu** (black pepper, *Piper nigrum*) and **Thippili** (long pepper, *Piper longum*) in equal parts. Its name was borrowed by the Sangam-age didactic poet Nallathanar for his ethical anthology *Thirikadugam*, in which every quatrain names three remedies for the soul as the drug names three remedies for the body.\n\n### 1. Purification (*சுத்தி*)\n- **Sukku**: the lime-bloomed outer skin is scraped off and the hand is lightly coated with lime paste or roasted, removing surface contaminants before pounding.\n- **Milagu**: soaked in buttermilk (*mor*) for 3 hours and sun-dried, a Siddha *suddhi* step that tempers its heat.\n- **Thippili**: lightly roasted in a dry iron pan until aromatic.\n\n### 2. Dry-Roasting & Pulverization (*வறுத்து இடித்தல்*)\n- Each ingredient is roasted separately in an iron **vanali** (வாணலி) on low flame. Separate roasting matters: pepper berries, long-pepper catkins and ginger hands have different moisture and oil content and scorch at different times.\n- The roasted drugs are pounded in a granite **ural** (உரல், stone mortar) with an iron-capped wooden **ulakkai** (உலக்கை, pestle), or ground on a flat **ammi** stone.\n- The powder is sifted through fine muslin cloth, the **vasthirakayam** (வஸ்திரகாயம்) process, giving a churnam fine enough to float on water.\n- The three powders are blended in **1:1:1** proportion by weight. Standard dose: 1 to 2 g (about half a *varagan*) with honey, ghee or warm water.\n\n### 3. Inji Lehyam Electuary (*இஞ்சி லேகியம்*)\n- Fresh tender Inji is ground and pressed to yield juice; the juice is allowed to stand so the white starch sediment settles and is discarded (starch causes fermentation).\n- Clarified juice is boiled with **palm or cane jaggery** in a bell-metal or brass cauldron with continuous stirring by a wooden ladle.\n- The syrup is tested for **paagu** (பாகு, candy stage): a drop rolled between finger and thumb draws a single thread (*nool-paagu*) or sets into a soft ball in cold water.\n- At this stage Thirikadugu, cumin, cardamom and coriander powders are folded in, followed by **cow ghee** and honey after the vessel cools slightly. The ghee acts as a lipid carrier (*anupanam*) and preservative, and the high sugar concentration (water activity below 0.7) gives a shelf-life of about one year.\n"
    },
    {
        "slug": "artifact-sun-cured-chalky-sukku-roots-clay-coated-storage-pots-and-brass-pestles",
        "file": "artifact-sun-cured-chalky-sukku-roots-clay-coated-storage-pots-and-brass-pestles.md",
        "category": "artifact",
        "name_en": "Sun-Cured Chalky Sukku Roots, Clay-Coated Storage Pots & Brass Pestles",
        "name_ta": "வெயிலில் உலர்ந்த வெண்சுக்குக் கிழங்குகள், களிமண் பூசிய சேமிப்புப் பானைகள் மற்றும் பித்தளை உலக்கைகள்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "mullai",
        "summary_en": "Material culture of the Tamil dry-ginger store: chalk-white lime-bloomed Sukku hands, cow-dung-and-clay-sealed earthenware kudam storage jars layered with neem leaves and ash against cigarette beetles, and heavy cast-brass kalvam mortars with brass pestles used to crush Sukku into churnam in household and vaidya pharmacies.",
        "summary_ta": "சுண்ணாம்புப் பூச்சால் வெண்மையான சுக்குக் கிழங்குகள், வேப்பிலையும் சாம்பலும் அடுக்கி மாட்டுச்சாணம் களிமண் பூசி மூடிய மண் குடங்கள், சுக்கைப் பொடியாக்கப் பயன்படும் கனமான பித்தளைக் கல்வம் மற்றும் பித்தளை உலக்கைகள் ஆகிய சுக்குச் சேமிப்புப் பொருள் பண்பாடு.",
        "sources": [
            "Arikamedu and Pattanam Excavation Reports",
            "Pathartha Guna Chinthamani",
            "Tamil Nadu Folk Kitchen Ethnography"
        ],
        "content": "# Sun-Cured Chalky Sukku Roots, Clay-Coated Storage Pots & Brass Pestles\n\nThe dry-ginger economy left behind a distinctive triad of objects in Tamil homes, temple kitchens and *vaidya* (Siddha physician) dispensaries: the cured root itself, the sealed earthen store-jar, and the brass crushing set.\n\n### 1. Chalky Sukku Hands (*வெண்சுக்கு*)\n- Lime-steeped, sun-cured ginger hands are bone-dry (8 to 10 percent moisture), dense, and coated in a powdery **calcium carbonate bloom** that rubs off white on the fingers. Fractured, they show a pale yellow, fibrous, resinous core.\n- Merchants judged quality by the \"ring\" when two hands were knocked together, by snap, and by the absence of grey mould at the nodes.\n- Cured Sukku retains potency for 2 to 3 years; the Tamil proverb *\"சுக்குக்கு மிஞ்சிய மருந்தில்லை\"* (\"there is no medicine beyond Sukku\") reflects its status as the universal household drug.\n\n### 2. Clay-Coated Storage Pots (*சுக்குக் குடம்*)\n- Sukku was stored in low-fired earthenware **kudam** or **thaazhi** jars. The jar mouth was closed with a potsherd lid and sealed with a paste of **cow dung and clay** (*saanam-mann*), making an airtight, humidity-buffering plug.\n- Inside, hands were layered with dried **neem leaves** (*Azadirachta indica*), *nochi* (*Vitex negundo*) leaves and dry wood ash, a repellent and desiccant combination against the cigarette beetle (*Lasioderma serricorne*) and drugstore beetle (*Stegobium paniceum*), the principal pests of stored spices.\n- Jars were kept on raised wooden lofts (*paran*) above the hearth, where wood smoke kept the store dry.\n\n### 3. Brass Kalvam & Pestles (*பித்தளைக் கல்வம்*)\n- Sukku is too hard and fibrous for a simple grinding stone; it was crushed in heavy cast **brass mortars** (*kalvam / ural*) with solid brass pestles weighing 1 to 2 kg.\n- The deep conical bowl prevents fibres and dust from flying out; brass resists the acidic oleoresin and does not discolour the powder as iron does.\n- Vaidya kalvams were often inscribed with the owner's name and lineage and passed down generations; smaller black-granite *kalvam* sets were used to triturate Sukku with honey for infant doses.\n"
    },
    {
        "slug": "artifact-inji-murabba-confections-sukku-malli-kaapi-pots-and-wooden-peeling-knives",
        "file": "artifact-inji-murabba-confections-sukku-malli-kaapi-pots-and-wooden-peeling-knives.md",
        "category": "artifact",
        "name_en": "Inji Murabba Confections, Sukku-Malli Kaapi Pots & Wooden Peeling Knives",
        "name_ta": "இஞ்சி முரப்பா இனிப்புகள், சுக்கு-மல்லிக் காப்பிப் பானைகள் மற்றும் மரத்தோல் சீவும் கத்திகள்",
        "era": "Medieval Era to Modern Era",
        "year_start": 1300,
        "year_end": 2026,
        "thinai": "marutham",
        "summary_en": "Everyday ginger objects of Tamil households: crystallised Inji Murabba candied in palm-sugar syrup and stored in glazed jaadi jars, earthenware and brass pots for brewing Sukku-Malli Kaapi (dry ginger and coriander seed coffee substitute sweetened with karupatti), and blunt wooden or bamboo peeling knives used to scrape tender ginger skin without staining.",
        "summary_ta": "பனங்கற்கண்டு பாகில் ஊறவைத்து உலர்த்திய இஞ்சி முரப்பா இனிப்புகள், கருப்பட்டி இனிப்புடன் சுக்கும் மல்லியும் சேர்த்துக் காய்ச்சும் சுக்கு-மல்லிக் காப்பிப் பானைகள், இஞ்சித் தோலைக் கறைபடாமல் சுரண்டும் மர மற்றும் மூங்கில் கத்திகள் ஆகிய இஞ்சிப் பொருட்கள்.",
        "sources": [
            "Tamil Folk Cuisine Oral Histories",
            "Madras Presidency District Gazetteers",
            "Siddha Home Remedies Compendia"
        ],
        "content": "# Inji Murabba Confections, Sukku-Malli Kaapi Pots & Wooden Peeling Knives\n\nBeyond the pharmacy, ginger entered the Tamil kitchen as candy, as a hot beverage, and through its own specialised tools.\n\n### 1. Inji Murabba (*இஞ்சி முரப்பா*)\n- Tender, low-fibre ginger (harvested at 5 to 6 months) is peeled, sliced into discs or cubes and **blanched** to leach excess pungency.\n- Slices are pricked with a thorn or bamboo needle so syrup penetrates, then cooked in successively stronger **palm-sugar (panangkarkandu) or cane-sugar syrups** over 3 to 5 days, an osmotic candying process that replaces cell water with sugar.\n- The drained pieces are rolled in fine sugar and sun-dried into translucent, amber, crystal-crusted confections, stored in salt-glazed ceramic **jaadi** jars. A piece of Inji Murabba after a feast was the classic digestive and travel-sickness remedy.\n\n### 2. Sukku-Malli Kaapi Pots (*சுக்கு மல்லிக் காப்பி*)\n- **Sukku-Malli Kaapi** is the Tamil village \"coffee\" that predates coffee: crushed Sukku, roasted **coriander seed (malli)**, a few black peppercorns and *thulasi* leaves boiled in water and sweetened with **karupatti** (palmyra jaggery).\n- It is brewed in squat, wide-mouthed earthenware **mann-sattis** or tinned brass *kooja* pots on the wood hearth, and served in brass tumblers, especially in the monsoon months and to labourers at dawn.\n- The earthen pot is preferred because it moderates the boil and its porous wall lends an earthy note; households kept a dedicated Sukku-kaapi pot that was never used for other cooking.\n\n### 3. Wooden & Bamboo Peeling Knives (*மரக் கத்தி*)\n- Fresh ginger skin is paper-thin; the oil cells lie immediately beneath. Households and pickle-makers used blunt-edged **wooden or split-bamboo scrapers**, or the edge of a teaspoon-like coconut-shell spoon, rather than steel.\n- Wood avoids the black iron-tannin stain and does not gouge into the aromatic cortex, keeping pickles (*inji oorugai*) and *inji-puli* (ginger-tamarind relish) bright and pungent.\n"
    },
    {
        "slug": "concept-gingerol-dehydration-to-shogaol-thermal-kinetics-and-pungency-amplification",
        "file": "concept-gingerol-dehydration-to-shogaol-thermal-kinetics-and-pungency-amplification.md",
        "category": "concept",
        "name_en": "Gingerol Dehydration to Shogaol: Thermal Kinetics & Pungency Amplification",
        "name_ta": "ஜிஞ்சரால் நீரிழப்பால் ஷோகாலாக மாறுதல்: வெப்ப இயக்கவியல் மற்றும் காரத்தன்மைப் பெருக்கம்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "kurinji",
        "summary_en": "The chemical concept explaining why dry Sukku is hotter than fresh Inji: [6]-gingerol, a beta-hydroxy ketone, undergoes heat- and acid-catalysed dehydration (loss of H2O) to form [6]-shogaol, an alpha,beta-unsaturated enone roughly twice as pungent, following reversible first-order kinetics that accelerate above 60 degrees C and at low pH, with retro-aldol cleavage to zingerone and hexanal as a competing pathway.",
        "summary_ta": "பச்சை இஞ்சியிலுள்ள ஜிஞ்சரால் என்ற பீட்டா-ஹைட்ராக்சி கீட்டோன் வெப்பத்தாலும் அமிலத்தாலும் நீர் மூலக்கூறை இழந்து இருமடங்கு காரமான ஷோகாலாக மாறும் முதல்-வரிசை வேதி இயக்கவியல் கொள்கை; இதனாலேயே சுக்கு இஞ்சியைவிடக் காரமும் வெப்பமும் மிக்கது.",
        "sources": [
            "Bhattarai, Tran & Duke (2001), J. Pharm. Sci.",
            "Jolad et al. (2004), Phytochemistry",
            "Siddha Gunapadam: Sukku Gunam"
        ],
        "content": "# Gingerol Dehydration to Shogaol: Thermal Kinetics & Pungency Amplification\n\nSiddha texts class fresh **Inji** and dry **Sukku** as two different drugs with different *gunam* (properties): Sukku is \"hotter\" (*ushnam*), drier and more strongly digestive. Modern phytochemistry explains the difference precisely.\n\n### 1. The Pungent Principles\n- Fresh ginger's pungency comes mainly from **[6]-gingerol** (with [8]- and [10]-gingerol homologues), 1 to 3 percent of dry weight. Structurally, gingerol is a **beta-hydroxy ketone**: a vanillyl (4-hydroxy-3-methoxyphenyl) head, a 3-keto group and a 5-hydroxyl on the alkyl chain.\n- On heating or drying, the 5-hydroxyl and an adjacent hydrogen are eliminated as water (**dehydration**), creating a C4=C5 double bond conjugated with the ketone: **[6]-shogaol**, an **alpha,beta-unsaturated ketone (enone)**. The name comes from Japanese *shoga*, ginger.\n\n### 2. Pungency Amplification\n- On the Scoville scale [6]-gingerol rates about 60,000 SHU while [6]-shogaol rates about 160,000 SHU, so shogaol is roughly **two to three times as pungent**. Both act on the **TRPV1** heat-pain receptor (the capsaicin receptor), but the conjugated enone of shogaol is a Michael acceptor that also activates **TRPA1**, producing the lingering, throat-burning heat characteristic of Sukku.\n\n### 3. Kinetics\n- The gingerol to shogaol reaction is **reversible and pseudo first-order**. Rate rises steeply with temperature (Arrhenius behaviour): negligible at room temperature, significant above 60 degrees C, and fast at 100 degrees C, where equilibrium is approached within hours.\n- It is **acid-catalysed**: maximal at pH 1 (as in the stomach) and slowest around pH 4. In alkaline lime-water the main effect is on surface tissues rather than the dehydration itself; most conversion occurs during prolonged sun-curing and later dry-roasting.\n- **Competing pathway**: at high moisture and heat, a **retro-aldol cleavage** splits gingerol into **zingerone** (sweet-spicy, far less pungent) and hexanal, which is why boiled ginger loses bite.\n- Typical ratios: fresh Inji contains almost no shogaol; sun-cured Sukku shows a gingerol:shogaol ratio of about 1:1 to 3:1; roasted Sukku in Thirikadugu shifts further toward shogaol.\n\n### 4. Pharmacological Consequence\n- Shogaols are more potent than gingerols as anti-inflammatory (COX-2 and NF-kB inhibition), antiemetic and antioxidant (Nrf2 activation) agents, consistent with the Siddha preference for Sukku over Inji in fevers, joint pain and *kapha* disorders.\n"
    },
    {
        "slug": "concept-thirikadugu-synergistic-bioavailability-enhancement-and-piperine-shogaol-mechanics",
        "file": "concept-thirikadugu-synergistic-bioavailability-enhancement-and-piperine-shogaol-mechanics.md",
        "category": "concept",
        "name_en": "Thirikadugu Synergistic Bioavailability Enhancement & Piperine-Shogaol Mechanics",
        "name_ta": "திரிகடுகு கூட்டுச்செயல் உயிர்க்கிடைப்புப் பெருக்கம் மற்றும் பைப்பரின்-ஷோகால் இயக்கவியல்",
        "era": "Sangam Era to Modern Era",
        "year_start": -200,
        "year_end": 2026,
        "thinai": "marutham",
        "summary_en": "The pharmacological concept of Thirikadugu as a yogavahi bio-enhancer: piperine from Milagu and Thippili inhibits CYP3A4 hepatic enzymes, P-glycoprotein efflux and UDP-glucuronosyltransferase glucuronidation, while shogaol and gingerol from Sukku increase gastrointestinal blood flow and enterocyte membrane fluidity, together raising plasma levels of co-administered drugs such as curcumin by up to 2000 percent.",
        "summary_ta": "மிளகு, திப்பிலியிலுள்ள பைப்பரின் கல்லீரல் CYP3A4 நொதிகளையும் P-கிளைக்கோபுரதக் கடத்தியையும் குளுகுரோனிடேஷனையும் தடுப்பதாலும், சுக்கிலுள்ள ஷோகால் குடல் இரத்த ஓட்டத்தைப் பெருக்குவதாலும், திரிகடுகு உடன் கொடுக்கப்படும் மருந்துகளின் உயிர்க்கிடைப்பைப் பலமடங்கு உயர்த்தும் யோகவாகி கொள்கை.",
        "sources": [
            "Atal, Zutshi & Rao (1981), J. Ethnopharmacol.",
            "Shoba et al. (1998), Planta Medica",
            "Johri & Zutshi (1992), Indian J. Physiol. Pharmacol."
        ],
        "content": "# Thirikadugu Synergistic Bioavailability Enhancement & Piperine-Shogaol Mechanics\n\nSiddha physicians add a pinch of **Thirikadugu** to a vast number of formulations not for its own action but as a **yogavahi** (catalytic carrier) that makes the other herbs \"reach\". In 1979 to 1981 the Regional Research Laboratory, Jammu (Atal, Zutshi and colleagues) coined the term **bioenhancer** for exactly this effect, isolating **piperine** as the first scientifically validated bioavailability enhancer.\n\n### 1. Piperine (from Milagu and Thippili)\n- **CYP3A4 inhibition**: piperine non-specifically inhibits hepatic and intestinal cytochrome P450 enzymes (CYP3A4, CYP1A2, CYP2D6), slowing first-pass oxidative metabolism of co-administered compounds.\n- **P-glycoprotein (P-gp, ABCB1) efflux inhibition**: piperine blocks the enterocyte efflux pump that ejects absorbed drugs back into the gut lumen.\n- **UGT glucuronidation inhibition**: piperine lowers UDP-glucuronosyltransferase activity and UDP-glucuronic acid levels, slowing phase-II conjugation and elimination. The classic demonstration (Shoba et al., 1998): 20 mg piperine raised human serum **curcumin** bioavailability by about **2000 percent**.\n- Piperine also increases brush-border microvilli length and membrane fluidity, enlarging the absorptive surface.\n\n### 2. Shogaol and Gingerol (from Sukku)\n- Sukku's shogaols and gingerols are **sialagogue and thermogenic**: they stimulate salivary, gastric and pancreatic secretion (lipase, amylase, trypsin) and bile flow.\n- They raise **splanchnic and gastrointestinal blood flow** and accelerate gastric emptying, so co-administered drugs reach the absorptive small intestine faster and are carried away from the enterocyte more quickly, sustaining the concentration gradient.\n- Ginger is itself a mild P-gp and CYP inhibitor and antiemetic, allowing nauseating drugs to be retained.\n\n### 3. Why Three, and Why Equal Parts\n- The three pungents act at **different sites**: Sukku on the stomach (secretion, motility, antiemesis), Thippili on the respiratory and intestinal mucosa (its piperine plus piperlongumine), Milagu on hepatic metabolism. The 1:1:1 ratio balances shogaol-driven gastric heat against piperine-driven metabolic inhibition.\n- Siddha theory frames this as Thirikadugu kindling **agni** (digestive fire) and clearing **aama** (undigested metabolic residue) that blocks the channels (*srotas*) through which medicines travel.\n"
    },
    {
        "slug": "concept-sangam-gastronomy-inji-appetizer-stimulation-and-siddha-pitta-kapha-balance",
        "file": "concept-sangam-gastronomy-inji-appetizer-stimulation-and-siddha-pitta-kapha-balance.md",
        "category": "concept",
        "name_en": "Sangam Gastronomy: Inji Appetizer Stimulation & Siddha Pitta-Kapha Balance",
        "name_ta": "சங்க உணவியல்: இஞ்சி பசித்தூண்டல் மற்றும் சித்த பித்த-கப சமநிலை",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "marutham",
        "summary_en": "The dietetic concept behind serving pungent Inji at the start of Tamil meals: fresh ginger with rock salt and lime juice as a pre-meal appetizer to stimulate cephalic-phase salivation and gastric secretion, the Siddha mukkuttram doctrine in which kaarppu (pungent taste) pacifies Kapha (Aiyam) while fresh Inji is milder on Pitta than dry Sukku, and the Sangam feast sequence of ginger pickles beside rice, ghee and meat.",
        "summary_ta": "உணவுக்கு முன் இஞ்சியை இந்துப்பு, எலுமிச்சைச் சாற்றுடன் உண்டு உமிழ்நீர், இரைப்பைச் சுரப்பைத் தூண்டும் பழக்கம், கார்ப்புச் சுவை ஐயத்தை (கபம்) தணிக்கும் சித்த முக்குற்றக் கொள்கை, பச்சை இஞ்சி சுக்கைவிடப் பித்தத்தை மிதமாகப் பாதிக்கும் தன்மை, சங்க விருந்துகளில் சோறு, நெய், ஊனுடன் இஞ்சி பரிமாறிய உணவியல் கொள்கை.",
        "sources": [
            "Pathitruppathu 30",
            "Porunaraatruppadai",
            "Thirukkural 944-945",
            "Siddha Noi Nadal Noi Mudhal Nadal"
        ],
        "content": "# Sangam Gastronomy: Inji Appetizer Stimulation & Siddha Pitta-Kapha Balance\n\n### 1. Ginger in the Sangam Feast\n- Sangam poems describe rich feasts of white rice, ghee, roasted meat and fish, toddy and pickles. *Pathitruppathu* 30 lists **inji** together with turmeric (*manjal*) and pepper among the produce of the hill-and-field country, and the *aatruppadai* guide-poems show bards fed with spiced meats and relishes, where pungent roots cut the richness of fat.\n- Ginger's role was the **opener and the closer**: a sliver of fresh Inji with rock salt (*induppu*) and lime juice before the meal, and ginger relishes (*inji-thuvaiyal*, *inji-puli*) alongside heavy dishes.\n\n### 2. Appetizer Physiology (*பசித்தூண்டல்*)\n- Pungent gingerols on the tongue trigger the **cephalic phase of digestion**: a vagal reflex that increases salivary amylase flow and primes gastric acid and pepsin secretion before food arrives.\n- Gingerols are **prokinetic** (5-HT3 and 5-HT4 modulation), speeding gastric emptying and relieving post-feast heaviness and nausea. Salt and citric acid with ginger amplify salivation further.\n- Thirukkural's chapter on diet (*Marundhu*, kurals 941 to 950) urges eating only after the previous meal is digested and in measure; ginger was the practical tool for kindling that appetite.\n\n### 3. Siddha Mukkuttram Balance\n- Siddha physiology rests on three humours, the **mukkuttram**: **Vatham** (wind), **Pitham** (fire/bile) and **Kabam / Aiyam** (phlegm/water). Of the six tastes (*aru-suvai*), **kaarppu** (pungent) increases Vatham and Pitham and decreases Kabam.\n- Ginger therefore is the prime **Kapha-reducing** food: it dries mucus, clears congestion, and counters the heaviness of rice, ghee and dairy.\n- **Inji versus Sukku**: fresh Inji is moister and gentler, suited to daily appetizers and *pitta* constitutions in moderation; Sukku is drier and hotter, reserved for *kapha* disorders, cold, cough and indigestion. The Siddha saying pairs them seasonally: Inji in the morning, Sukku at noon, *kadukkai* (myrobalan) at night, for lasting youth.\n"
    },
    {
        "slug": "institution-western-ghats-rhizome-foraging-guilds-and-ayurvedic-siddha-marundhu-merchants",
        "file": "institution-western-ghats-rhizome-foraging-guilds-and-ayurvedic-siddha-marundhu-merchants.md",
        "category": "institution",
        "name_en": "Western Ghats Rhizome Foraging Guilds & Ayurvedic-Siddha Marundhu Merchants",
        "name_ta": "மேற்குத் தொடர்ச்சி மலைக் கிழங்கு சேகரிப்புக் குழுக்கள் மற்றும் ஆயுர்வேத-சித்த மருந்து வணிகர்கள்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "kurinji",
        "summary_en": "The institutional chain that moved ginger from forest to pharmacy: Kurinji hill tribes such as the Kadar, Muthuvan and Paliyar who foraged wild Zingiber and cultivated swidden ginger plots in the Anamalai and Palani hills, the naattu marundhu kadai (country drug-shop) merchants and nanadesi trade guilds who bought, cured and graded Sukku, and the temple and royal vaidya dispensaries that compounded Thirikadugu.",
        "summary_ta": "ஆனைமலை, பழனி மலைகளில் காட்டு இஞ்சியைச் சேகரித்தும் புனப் பயிரிட்டும் வந்த காடர், முதுவர், பளியர் போன்ற குறிஞ்சி மலைவாழ் மக்கள், சுக்கை வாங்கிப் பதப்படுத்தித் தரம் பிரித்த நாட்டு மருந்துக் கடை வணிகர்கள் மற்றும் நானாதேசி வணிகக் குழுக்கள், திரிகடுகு செய்த கோயில் மற்றும் அரச வைத்தியசாலைகள் ஆகிய நிறுவனச் சங்கிலி.",
        "sources": [
            "Periplus of the Erythraean Sea 56",
            "Tirumukkudal Venkatesa Perumal Temple Inscription (1069 CE)",
            "Anamalai Tribal Ethnobotany Surveys"
        ],
        "content": "# Western Ghats Rhizome Foraging Guilds & Ayurvedic-Siddha Marundhu Merchants\n\nGinger reached the Siddha physician's *kalvam* through a three-tier institutional chain that operated from the Sangam age into the twentieth century.\n\n### 1. Hill Foragers and Swidden Cultivators (*குறிஞ்சி மலைவாழ் மக்கள்*)\n- In the **Anamalai, Palani and Agasthyamalai** ranges of the southern Western Ghats, forest communities such as the **Kadar**, **Muthuvan**, **Malasar** and **Paliyar** dug wild *Zingiber* species (*kaattu inji*, including *Zingiber zerumbet* and *Z. nimmonii*) and cultivated true ginger in shifting forest clearings (*punam*).\n- Sangam poems describe the Kurinji folk (*kuravar*) bartering hill produce such as honey, pepper, roots and tubers in the plains for salt, rice and cloth. Ginger moved down on head-load and pack-bullock along ghat passes such as the **Palghat Gap**.\n\n### 2. Curing Merchants and Trade Guilds\n- Plains merchants bought fresh rhizomes and ran the lime-steeping and sun-curing yards, then graded and bagged Sukku. The **naattu marundhu kadai** (நாட்டு மருந்துக் கடை, country raw-drug shop), still found in every Tamil town bazaar, sold Sukku, Milagu, Thippili and some 300 other raw drugs.\n- Long-distance trade was handled by itinerant merchant guilds such as the **Nanadesi Ainnurruvar** (\"Five Hundred of the Thousand Directions\") and **Manigramam**, whose inscriptions list pepper and spices among guarded commodities. The *Periplus* records pepper and malabathrum shipped from Muziris and Nelcynda; ginger (Greek *zingiberi*, from Tamil-Malayalam *inji-ver*, \"ginger root\") joined this Roman spice trade.\n\n### 3. Temple and Royal Dispensaries (*ஆதுலர் சாலை*)\n- The 1069 CE inscription of Virarajendra Chola at the **Tirumukkudal** Venkatesa Perumal temple records an endowed hospital (*athular salai*) with physicians, a surgeon and herb-gatherers, and a stock list of medicines; pungent drug compounds are among the remedies.\n- Hereditary Siddha *vaidyas* and temple dispensaries bought Sukku and the other pungents in bulk, compounded Thirikadugu churnam and lehyams, and dispensed them free to pilgrims and the poor.\n"
    },
    {
        "slug": "place-pollachi-ancient-kongu-inji-ginger-and-sukku-curing-haven",
        "file": "place-pollachi-ancient-kongu-inji-ginger-and-sukku-curing-haven.md",
        "category": "place",
        "name_en": "Pollachi: Ancient Kongu Inji Ginger & Sukku Curing Haven",
        "name_ta": "பொள்ளாச்சி: பண்டைய கொங்கு இஞ்சி மற்றும் சுக்கு பதப்படுத்தும் மையம்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "mullai",
        "summary_en": "Pollachi in the Kongu Nadu region, at the foot of the Anamalai hills beside the Palghat Gap, where monsoon-fed red laterite soils of the Aliyar and Palar valleys grew ginger, the weekly shandy (santhai) markets traded hill rhizomes and Sukku, and dry winds funnelling through the Palghat Gap made it a natural sun-curing yard linking the Kongu plains to the Kerala Malabar spice coast and Roman coin hoards along the Noyyal.",
        "summary_ta": "கொங்கு நாட்டில் ஆனைமலை அடிவாரத்தில் பாலக்காட்டுக் கணவாய் அருகில் அமைந்த பொள்ளாச்சி; ஆழியாறு, பாலாறு பள்ளத்தாக்குகளின் செம்மண் நிலங்களில் இஞ்சி விளைந்ததும், வாரச் சந்தைகளில் மலைக் கிழங்குகளும் சுக்கும் விற்கப்பட்டதும், கணவாய் வழியே வீசும் வறண்ட காற்று சுக்கு உலர்த்த ஏற்றதுமான வணிக மையம்.",
        "sources": [
            "Coimbatore District Gazetteer",
            "Roman Coin Hoards of the Kongu Region (Pollachi, Vellalur)",
            "Kongu Mandala Sathagam"
        ],
        "content": "# Pollachi: Ancient Kongu Inji Ginger & Sukku Curing Haven\n\n**Pollachi** (பொள்ளாச்சி) lies in the southern **Kongu Nadu** region, at the foot of the **Anamalai** hills and on the eastern mouth of the **Palghat Gap**, the only major break in the Western Ghats.\n\n### 1. Geography and Agro-ecology\n- The red laterite and loamy soils of the **Aliyar** and **Palar** river valleys, fed by the south-west monsoon spilling through the Palghat Gap, suit rhizome crops: ginger, turmeric and the arrowroot-like *koova*.\n- Immediately above, the Anamalai forests supplied wild ginger and forest-grown rhizomes gathered by the Kadar, Malasar and Muthuvan.\n- From November to April, **dry north-east winds funnel through the Palghat Gap** with low humidity and steady sunshine, ideal for the 8 to 10 day sun-curing of lime-steeped ginger into Sukku without mould.\n\n### 2. The Santhai Market Town\n- Pollachi grew around its great weekly **santhai** (சந்தை, shandy), famous for cattle, jaggery, coconut and hill produce. Hill rhizomes, cured Sukku, pepper and cardamom came down to be traded against plains grain, salt and cloth.\n- The town's name is traditionally derived from *pozhil vaachi*, \"the abundant grove\".\n\n### 3. Ancient Trade Links\n- Pollachi and its neighbourhood (Vellalur, Kaliyapuram) have yielded some of the largest **Roman coin hoards** in India, mostly silver denarii of Augustus and Tiberius, marking the overland route from the Kaveri delta and Karur across Kongu and through the Palghat Gap to the Malabar pepper ports of **Muziris**.\n- Ginger, pepper and beryl from Kongu moved west along this route. Sangam-era Kongu was contested by the Chera, Chola and Pandya kings precisely for control of this spice and gem corridor.\n- In the colonial period Pollachi remained a major dry-ginger and jaggery market feeding Coimbatore and Cochin.\n"
    },
    {
        "slug": "text-sangam-and-siddha-medical-classics-on-inji-sukku-and-thirikadugu-panacea",
        "file": "text-sangam-and-siddha-medical-classics-on-inji-sukku-and-thirikadugu-panacea.md",
        "category": "text",
        "name_en": "Sangam & Siddha Medical Classics on Inji, Sukku & the Thirikadugu Panacea",
        "name_ta": "இஞ்சி, சுக்கு மற்றும் திரிகடுகு சர்வரோக நிவாரணி பற்றிய சங்க மற்றும் சித்த மருத்துவ நூல்கள்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "The literary corpus on ginger: Pathitruppathu and other Sangam poems naming inji among hill produce, Nallathanar's post-Sangam didactic anthology Thirikadugam whose 100 venba quatrains each name three moral remedies by analogy with the tri-pungent drug, Thirumoolar's Thirumanthiram and the Agathiyar and Theraiyar Siddha corpus including Gunapadam materia medica verses praising Sukku, and the proverb that no medicine surpasses Sukku.",
        "summary_ta": "இஞ்சியை மலை விளைபொருளாகக் குறிப்பிடும் பதிற்றுப்பத்து உள்ளிட்ட சங்கப் பாடல்கள், மூன்று காரச் சரக்குகள் போல ஒவ்வொரு வெண்பாவிலும் மூன்று அறநெறி மருந்துகளைக் கூறும் நல்லாதனாரின் திரிகடுகம், சுக்கின் குணங்களைப் போற்றும் அகத்தியர், தேரையர் குணபாட நூல்கள், 'சுக்குக்கு மிஞ்சிய மருந்தில்லை' என்ற பழமொழி ஆகிய இலக்கியத் தொகுப்பு.",
        "sources": [
            "Thirikadugam (Nallathanar), Pathinenkilkanakku",
            "Pathitruppathu 30",
            "Agathiyar Gunavagadam",
            "Theraiyar Yamaga Venba"
        ],
        "content": "# Sangam & Siddha Medical Classics on Inji, Sukku & the Thirikadugu Panacea\n\n### 1. Sangam Poetry\n- *Pathitruppathu* 30, praising the Chera king, lists **inji** with **manjal** (turmeric), sweet fruits and hill produce piled in the fertile land: ginger and turmeric are the paired rhizomes of the Tamil hill-and-field economy.\n- *Malaipadukadam* and *Kurinjippattu* catalogue the roots, tubers and spices of the Kurinji hills, and *Perumpanaatruppadai* depicts pepper sacks moving on donkey-back along the trade routes on which ginger travelled.\n\n### 2. Thirikadugam, the Ethical Tri-Pungent\n- **Thirikadugam** (திரிகடுகம்) by **Nallathanar** is one of the eighteen post-Sangam minor classics (*Pathinenkilkanakku*, c. 3rd to 6th century CE). Its title is the drug's name: just as **Sukku, Milagu and Thippili** together cure bodily disease, each of its **100 venba quatrains** names **three** virtues, vices or acts that cure or cause moral sickness.\n- Its preface states the analogy outright, making the text itself an early literary witness that the 1:1:1 tri-pungent formula was already common knowledge across Tamil society.\n\n### 3. Siddha Medical Corpus\n- The **Agathiyar** corpus (*Agathiyar Gunavagadam*, *Agathiyar Vaithiya Kaviyam*) and **Theraiyar**'s works (*Theraiyar Yamaga Venba*, *Theraiyar Gunavagadam*) form the core of Siddha *gunapadam* (materia medica). They describe Sukku as **kaarppu** (pungent) in taste, **veppam** (hot) in potency and pungent in post-digestive effect, curing *kabam*, cough, indigestion, flatulence, rheumatism and fever.\n- **Thirumoolar's Thirumanthiram** sets out the Siddha body philosophy (\"those who neglect the body destroy the soul\") that frames food and herb as medicine.\n- Folk Siddha verse gives the rasayana triad: **Inji at dawn, Sukku at noon, Kadukkai at dusk** keeps the body ever young.\n- The proverb **\"சுக்குக்கு மிஞ்சிய மருந்தில்லை, சுப்பிரமணியருக்கு மிஞ்சிய தெய்வமில்லை\"** (\"no medicine beyond Sukku, no god beyond Subramanya\") pairs dry ginger with the Kurinji hill god Murugan himself.\n"
    }
]

EDGES = [
    [
        "technology-inji-rhizome-peeling-lime-water-steeping-and-sukku-sun-curing",
        "produces",
        "artifact-sun-cured-chalky-sukku-roots-clay-coated-storage-pots-and-brass-pestles",
        "material_culture",
        "Sangam Era to Modern Era",
        "Lime-steeping and sun-curing yield the chalk-white Sukku hands stored in sealed clay jars and crushed in brass kalvams",
        "Craft Observation"
    ],
    [
        "technology-inji-rhizome-peeling-lime-water-steeping-and-sukku-sun-curing",
        "embodies",
        "concept-gingerol-dehydration-to-shogaol-thermal-kinetics-and-pungency-amplification",
        "material_culture",
        "Sangam Era to Modern Era",
        "Prolonged sun-curing drives partial dehydration of gingerol into the more pungent shogaol",
        "Chemical Analysis"
    ],
    [
        "technology-thirikadugu-tri-pungent-pulverization-and-inji-lehyam-decoction",
        "embodies",
        "concept-thirikadugu-synergistic-bioavailability-enhancement-and-piperine-shogaol-mechanics",
        "material_culture",
        "Sangam Era to Modern Era",
        "The 1:1:1 Sukku-Milagu-Thippili churnam realises the piperine and shogaol bio-enhancer synergy",
        "Pharmacological Studies"
    ],
    [
        "technology-thirikadugu-tri-pungent-pulverization-and-inji-lehyam-decoction",
        "utilizes",
        "artifact-sun-cured-chalky-sukku-roots-clay-coated-storage-pots-and-brass-pestles",
        "material_culture",
        "Sangam Era to Modern Era",
        "Thirikadugu compounding draws cured Sukku from clay stores and pounds it in brass mortars and pestles",
        "Ethnoarchaeology"
    ],
    [
        "artifact-inji-murabba-confections-sukku-malli-kaapi-pots-and-wooden-peeling-knives",
        "embodies",
        "concept-sangam-gastronomy-inji-appetizer-stimulation-and-siddha-pitta-kapha-balance",
        "material_culture",
        "Medieval Era to Modern Era",
        "Candied ginger digestives and Sukku-Malli Kaapi express the Kapha-reducing, appetite-kindling dietetics of ginger",
        "Culinary Ethnography"
    ],
    [
        "concept-gingerol-dehydration-to-shogaol-thermal-kinetics-and-pungency-amplification",
        "enables",
        "concept-thirikadugu-synergistic-bioavailability-enhancement-and-piperine-shogaol-mechanics",
        "material_culture",
        "Sangam Era to Modern Era",
        "Shogaol formed during curing and roasting is the Sukku component of Thirikadugu's synergy",
        "Phytochemistry"
    ],
    [
        "institution-western-ghats-rhizome-foraging-guilds-and-ayurvedic-siddha-marundhu-merchants",
        "operates_in",
        "place-pollachi-ancient-kongu-inji-ginger-and-sukku-curing-haven",
        "material_culture",
        "Sangam Era to Modern Era",
        "Anamalai hill foragers and Sukku curing merchants converged on the Pollachi santhai at the Palghat Gap",
        "Historical Geography"
    ],
    [
        "place-pollachi-ancient-kongu-inji-ginger-and-sukku-curing-haven",
        "cultivates",
        "technology-inji-rhizome-peeling-lime-water-steeping-and-sukku-sun-curing",
        "material_culture",
        "Sangam Era to Modern Era",
        "Dry Palghat Gap winds and Aliyar valley ginger fields made Pollachi a natural sun-curing yard",
        "Geographical Survey"
    ],
    [
        "institution-western-ghats-rhizome-foraging-guilds-and-ayurvedic-siddha-marundhu-merchants",
        "administers",
        "technology-thirikadugu-tri-pungent-pulverization-and-inji-lehyam-decoction",
        "material_culture",
        "Sangam Era to Modern Era",
        "Naattu marundhu merchants and temple vaidya dispensaries compounded and dispensed Thirikadugu and lehyams",
        "Epigraphical Records"
    ],
    [
        "text-sangam-and-siddha-medical-classics-on-inji-sukku-and-thirikadugu-panacea",
        "documents",
        "concept-thirikadugu-synergistic-bioavailability-enhancement-and-piperine-shogaol-mechanics",
        "material_culture",
        "Sangam Era to Modern Era",
        "Nallathanar's Thirikadugam and the Agathiyar-Theraiyar gunapadam record the tri-pungent formula and its yogavahi role",
        "Literary Analysis"
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
