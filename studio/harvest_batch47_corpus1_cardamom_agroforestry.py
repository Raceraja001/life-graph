#!/usr/bin/env python3
"""
Harvester: Batch 47 - Ancient Tamil Cardamom & Hill-Forest Spice Agroforestry, Shade Curing & Kurinji Caravan Trade
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
        "slug": "text-sangam-and-silappadikaram-on-elam-cardamom-and-kurinji-forest-aromatics",
        "category": "text",
        "file": "text-sangam-and-silappadikaram-on-elam-cardamom-and-kurinji-forest-aromatics.md",
        "name_en": "Malaipadukadam, Kurinjippattu & Silappadikaram on Elam Cardamom and Hill Aromatics",
        "name_ta": "மலைபடுகடாம், குறிஞ்சிப்பாட்டு மற்றும் சிலப்பதிகாரத்தில் ஏலம் மற்றும் குறிஞ்சி மலை நறுமணப் பொருட்கள்",
        "era": "Sangam to Post-Sangam Era",
        "year_start": -300,
        "year_end": 600,
        "thinai": "kurinji",
        "summary_en": "Classical Tamil literary accounts in Malaipadukadam, Kurinjippattu, and Silappadikaram documenting wild and semi-domesticated hill cardamom (elam / elakkai), black pepper, eaglewood, and sandalwood harvested by Kuravar forest communities in the Western Ghats.",
        "summary_ta": "மலைபடுகடாம், குறிஞ்சிப்பாட்டு மற்றும் சிலப்பதிகாரம் ஆகியவற்றில் மேற்குத் தொடர்ச்சி மலையின் குறிஞ்சி நிலக் குறவர்கள் சேகரித்த ஏலம் (ஏலக்காய்), மிளகு, அகில் மற்றும் சந்தனம் பற்றிய இலக்கியப் பதிவுகள்.",
        "sources": [
            "Malaipadukadam",
            "Kurinjippattu",
            "Silappadikaram"
        ],
        "content": "# Sangam & Silappadikaram Accounts of Hill Cardamom (Elam)\n\nClassical Tamil texts celebrate *elam* (*Elettaria cardamomum*) as a signature aromatic treasure of the *Kurinji* montane forests of the Western Ghats:\n\n**Literary Attestations:**\n- **Malaipadukadam & Kurinjippattu**: The ten-idyll poems describe the moist, cloud-wrapped slopes of the southern hills where clump-forming cardamom plants flourish beneath towering forest trees alongside wild ginger (*inji*), turmeric (*manjal*), and black pepper vines (*kari*).\n- **Silappadikaram Aromatics & Trade**: In *Silappadikaram*, *elam* is listed among the tribute gifts brought by hill dwellers (*Kunra-Kuravar*) and as one of the five fragrant chewables (*pasam*) and hair-perfuming aromatics traded in the bazaar streets of Puhar and Madurai.\n- **Etymological Continuity**: The Tamil word *elam* passed into Sanskrit (*ela*) and Mediterranean trade vocabularies as the premier small green cardamom of South India."
    },
    {
        "slug": "concept-elettaria-cardamomum-understory-shade-ecology-and-terpinyl-acetate-chemistry",
        "category": "concept",
        "file": "concept-elettaria-cardamomum-understory-shade-ecology-and-terpinyl-acetate-chemistry.md",
        "name_en": "Elettaria cardamomum Understory Shade Ecology, Basal Panicles & Terpinyl Acetate Chemistry",
        "name_ta": "ஏலக்காய்த் தாவரத்தின் பசுமைமாறாக் காட்டு நிழல் சூழலியல், அடித்தண்டுப் பூங்கொத்து மற்றும் நறுமண வேதியியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Agroforestry ecology and essential oil biochemistry of small cardamom (Elettaria cardamomum): filtered 50-60% evergreen canopy shade, leaf-mould humus moisture retention, prostrate basal panicle flowering, and synthesis of 1,8-cineole and alpha-terpinyl acetate.",
        "summary_ta": "சிறு ஏலத்தின் (Elettaria cardamomum) காட்டு நிழல் சூழலியல்: 50-60% மர நிழல், இலைமக்கு ஈரப்பதம், வேரடிப் பூங்கொத்து மகரந்தச் சேர்க்கை மற்றும் 1,8-சினியோல், ஆல்பா-டெர்பினைல் அசிடேட் நறுமண எண்ணெய் வேதியியல்.",
        "sources": [
            "Flora of the Presidency of Madras",
            "Indian Cardamom Research Institute Monographs",
            "Western Ghats Shola Agroforestry Studies"
        ],
        "content": "# Elettaria cardamomum Shade Ecology & Essential Oil Chemistry\n\nSmall green cardamom (*Elettaria cardamomum*, family Zingiberaceae) is an obligate shade-loving perennial native to the mid-elevation evergreen shola forests (600–1,500 m) of the Western Ghats:\n\n**Botanical & Biochemical Principles:**\n- **Filtered Canopy & Leaf-Mulch Microclimate**: Cardamom rhizomes thrive only under a regulated two-tier forest canopy (*Vernonia*, *Cedrela toona*, *Artocarpus*, and jackfruit trees) that filters 50–60% of direct sunlight, buffers monsoon wind-throw, and deposits deep leaf-litter humus that holds moisture without waterlogging.\n- **Basal Panicle Morphology**: Slender flowering shoots (*saradu*) emerge directly from the base of the leafy pseudostems and trail across the forest floor (`Mysore`, `Malabar`, and `Vazhukka` ecotypes), relying on native solitary and colonial wild bees (*Apis cerana*) for cross-pollination.\n- **Volatile Oil Chemistry**: The sweet, cooling camphoraceous-citrus aroma of Tamil hill cardamom arises from the balanced ratio of two monoterpenes inside the seed arils: **alpha-terpinyl acetate** (imparting sweet floral-spicy notes) and **1,8-cineole** (imparting brisk eucalyptus-like freshness)."
    },
    {
        "slug": "technology-basal-panicle-selective-picking-and-alkaline-ash-chlorophyll-washing",
        "category": "technology",
        "file": "technology-basal-panicle-selective-picking-and-alkaline-ash-chlorophyll-washing.md",
        "name_en": "Selective Karukkai Capsule Picking & Alkaline Wood-Ash/Soda Chlorophyll Fixing Wash",
        "name_ta": "கருக்காய் பருவத் தெரிந்தெடுப்பு அறுவடை மற்றும் பச்சையம் காக்கும் காரச் சாம்பல் நீர் கழுவும் தொழில்நுட்பம்",
        "era": "Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Harvesting and pre-curing wet processing of green cardamom: multi-round selective hand-picking of three-valved capsules at the black-seeded karukkai stage with short pedicels, followed by immersion in clarified wood-ash lye or 2% alkali solution to stabilize epicarp chlorophyll.",
        "summary_ta": "ஏலக்காய் அறுவடை மற்றும் முன்பதப்படுத்தும் நுட்பம்: விதைகள் கருப்பாக முற்றிய கருக்காய் பருவத்தில் காம்புடன் கிள்ளி எடுத்தல் மற்றும் தோலின் பச்சை நிறம் மாறாமல் காக்க மரச்சாம்பல் கார நீரில் கழுவுதல்.",
        "sources": [
            "Cardamom Hills Plantation Ethnographies",
            "Traditional Spice Processing Manuals of Madurai and Theni",
            "Spices Board Post-Harvest Technology Guides"
        ],
        "content": "# Selective Karukkai Picking & Alkaline Chlorophyll-Fixing Wash\n\nBecause cardamom flowers open sequentially along the basal panicle over several months, indiscriminate stripping ruins both yield and essential oil content:\n\n**Harvesting & Wet Pre-Treatment:**\n1. **Multi-Round Selective Picking (*Eddupu*)**: Skilled pickers traverse the shaded slopes every 25–30 days, inspecting the trailing panicles by touch and sight. Only capsules at the exact *karukkai* stage—where the outer pericarp is taut and deep green while the internal seeds have just turned from white (*vellai-kai*) to dark brown-black—are snipped with the short stalk (*kambu*) intact. Over-ripe yellow pods (*pazhakai*) split open during drying.\n2. **Soil & Mucilage Scrubbing**: Freshly picked pods are immediately washed in cold mountain stream water to remove forest soil and floral remnants.\n3. **Alkaline Chlorophyll Stabilization**: Before thermal curing, capsules are dipped for 10 minutes in a decanted solution of clean wood-ash lye (*saambal-neer*) or mild sodium bicarbonate/carbonate. The alkaline bath neutralizes organic plant acids that would otherwise convert bright green chlorophyll into dull olive-brown pheophytin during heat drying."
    },
    {
        "slug": "technology-odai-flue-kiln-thermal-curing-and-coir-mat-chaff-winnowing",
        "category": "technology",
        "file": "technology-odai-flue-kiln-thermal-curing-and-coir-mat-chaff-winnowing.md",
        "name_en": "Odai Wood-Flue Kiln Thermal Curing, Controlled Dehydration & Coir-Mat Calyx Polishing",
        "name_ta": "ஓடை விறகுச் சூளை வெப்ப உலர்த்தல், ஈரப்பதக் கட்டுப்பாடு மற்றும் கயிற்றுப் பாய் தேய்ப்புப் பளபளப்பூட்டல்",
        "era": "Medieval to Modern Era",
        "year_start": 900,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Thermal engineering of cardamom curing houses (odai / thotti): indirect wood-fired furnace flues heating tiered wire-mesh or bamboo racks in darkened chambers from 45°C to 55°C over 36 hours to reduce moisture from 80% to 10% without volatilizing essential oils, followed by hot-polishing.",
        "summary_ta": "ஏலக்காய் உலர்த்தும் 'ஓடை' சூளைத் தொழில்நுட்பம்: புகை படாமல் மறைமுக வெப்பக் குழாய்கள் மூலம் 45°C–55°C வெப்பநிலையில் 36 மணி நேரம் உலர்த்தி, கயிற்றுப் பாயில் தேய்த்துக் காம்பு நீக்கிப் பளபளப்பாக்குதல்.",
        "sources": [
            "Bodinayakanur and Cumbum Valley Curing House Records",
            "Travancore and Madurai Cardamom Curing Traditions",
            "Post-Harvest Engineering of Plantation Spices"
        ],
        "content": "# Odai Flue-Kiln Thermal Curing & Coir-Mat Calyx Polishing\n\nDirect sun-drying bleaches green cardamom capsules to straw-white and cracks their three valves; consequently, Western Ghats curers perfected indirect thermal kiln drying (*Odai* or * Vathal-Pura*):\n\n**Three-Stage Thermal Curing Cycle:**\n1. **Indirect Flue-Pipe Kiln (*Odai*)**: Inside a thick-walled stone and mud-plastered curing chamber excluded from sunlight, firewood burned in an external furnace sends hot gases through horizontal iron or masonry flue pipes beneath tiered bamboo or wire trays loaded with wet capsules.\n2. **Stepped Temperature Curve**:\n   - *Sweating Phase (0–12 hrs, 43–45°C)*: Vents are opened to expel surface moisture rapidly without cooking the pericarp.\n   - *Active Drying Phase (12–30 hrs, 50–55°C)*: Trays are rotated as internal moisture drops; temperature is strictly capped below 58°C to prevent evaporation of volatile 1,8-cineole and alpha-terpinyl acetate.\n   - *Final Crisp Phase (30–36 hrs, 48°C)*: Moisture is brought down from ~80% fresh weight to 9–10% dry weight.\n3. **Hot Rubbing & Winnowing**: While still warm and brittle from the kiln, dried capsules are rubbed across rough coir mats or bamboo sieves to snap off shriveled floral calyx beaks (*mooku*) and stalks, then winnowed in bamboo *muram* fans."
    },
    {
        "slug": "concept-karukkai-pazhakai-capsule-ripeness-chlorophyll-retention-and-grading-metrics",
        "category": "concept",
        "file": "concept-karukkai-pazhakai-capsule-ripeness-chlorophyll-retention-and-grading-metrics.md",
        "name_en": "Karukkai vs Pazhakai Ripeness Physiology, Litre-Weight Bulk Density & Sieve Grading",
        "name_ta": "கருக்காய் மற்றும் பழக்காய் முதிர்ச்சி நிலைகள், லிட்டர் எடை அடர்த்தி மற்றும் சல்லடை தர வகைப்பாடு",
        "era": "Medieval to Modern Era",
        "year_start": 900,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Metrology and quality science of cured Tamil hill cardamom: distinguishing immature vellai-kai, optimal black-seeded karukkai, and split pazhakai pods, alongside bulk density measurement (grams per litre) and round-mesh sieve grading (6 mm to 8+ mm bold).",
        "summary_ta": "ஏலக்காயின் தர நிர்ணய அறிவியல்: வெள்ளைக்காய், கருக்காய், பழக்காய் முதிர்ச்சி நிலை வேறுபாடுகள், ஒரு லிட்டர் கொள்ளளவு எடை (Bulk Density) மற்றும் 6 மி.மீ முதல் 8 மி.மீ வரையான சல்லடைப் பிரிப்பு.",
        "sources": [
            "Bodinayakanur Cardamom Auction & Grading Standards",
            "Agmark Alappey Green Cardamom Specifications",
            "Traditional South Indian Spice Metrology"
        ],
        "content": "# Karukkai Ripeness Physiology, Litre-Weight & Sieve Grading\n\nIn the spice markets of Bodinayakanur, Cumbum, and Madurai, the commercial and medicinal value of cardamom is governed by three physical metrics:\n\n**Quality & Grading Science:**\n- **Three Ripeness Stages**:\n  1. *Vellai-Kai* (Immature): Picked too early; white seeds shrivel during kiln curing, yielding chaffy, low-density pods with weak aroma.\n  2. *Karukkai* (Physiological Optimum): Full-sized green capsule whose mucilage-coated seeds have just turned dark black; cures into a tight, unsplit, parrot-green three-angled pod packed with volatile oil.\n  3. *Pazhakai* (Over-Ripe): Yellowing pericarp splits along the three sutures during drying, exposing seeds to oxidative aroma loss.\n- **Bulk Density (Litre-Weight)**: Merchants measure a struck dry volume in a standardized brass cylindrical measure (*padi* or litre vessel). Premium *Karukkai* lots weigh **430 to 480+ grams per litre**, whereas immature chaffy lots fall below 350 g/L.\n- **Round-Hole Sieve Calibration**: Cured pods are passed through perforated brass sieves into *Extra Bold* (8 mm+), *Bold* (7–8 mm), *Medium* (6–7 mm), and *Splits/Seeds* (*Thool*)."
    },
    {
        "slug": "artifact-bold-alappey-green-cardamom-pods-and-aromatic-seed-essential-oils",
        "category": "artifact",
        "file": "artifact-bold-alappey-green-cardamom-pods-and-aromatic-seed-essential-oils.md",
        "name_en": "Kiln-Cured Parrot-Green Cardamom Capsules (Elakkai), Split Pods & Decorticated Aril Seeds",
        "name_ta": "பச்சைக் கிளிநிற ஏலக்காய், முப்பட்டைக் காய்கள் மற்றும் நறுமண ஏல அரிசி விதைகள்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Material trade forms of Western Ghats small cardamom: kiln-cured three-sided parrot-green whole capsules (Alappey/Bodi Green), sun-bleached white capsules, decorticated sticky black seeds (ela-arisi) sheathed in papery arils, and steam-distilled essential oil.",
        "summary_ta": "மேற்குத் தொடர்ச்சி மலை ஏலக்காயின் வணிக வடிவங்கள்: சூளையில் பதப்படுத்திய கிளிப்பச்சை முழு ஏலக்காய்கள், வெயிலில் உலர்த்திய வெள்ளை ஏலம் மற்றும் தோல் உரித்த நறுமண 'ஏல அரிசி' விதைகள்.",
        "sources": [
            "Silappadikaram",
            "Madurai and Bodinayakanur Spice Trade Inventories",
            "Pharmacognosy of Elettaria cardamomum"
        ],
        "content": "# Kiln-Cured Green Cardamom Capsules & Ela-Arisi Seeds\n\nThe cured fruit of *Elettaria cardamomum* enters culinary, ritual, and maritime commerce in distinct morphological grades:\n\n**Artifact & Commodity Forms:**\n- **Kiln-Cured Green Capsules (*Pachai Elakkai*)**: Ovoid, distinctly three-sided (*muppattai*) capsules measuring 7 to 15 mm long with a finely ribbed, fibrous green pericarp. The tough outer husk acts as a natural hermetic capsule sealing 15 to 20 angular, rugose brownish-black seeds against air and light.\n- **Ela-Arisi (Decorticated Seeds & Aril Membrane)**: Inside each of the three locules, the dark seeds are enveloped in a thin, colourless, mucilaginous membrane (aril). Nearly 95% of the volatile essential oil resides inside the seed coat and aril rather than the fibrous green husk.\n- **Temple *Theertham* & Royal *Tambulam***: Whole green pods are crushed into temple *panchamirtham* (in the Palani–Kodai hills belt), infused into sacred *theertham* water alongside camphor and cloves, and folded into betel-leaf *tambulam* quids."
    },
    {
        "slug": "artifact-kombu-vazhi-pack-bullock-panniers-and-bamboo-picking-baskets",
        "category": "artifact",
        "file": "artifact-kombu-vazhi-pack-bullock-panniers-and-bamboo-picking-baskets.md",
        "name_en": "Malai-Koodai Bamboo Picking Baskets, Pack-Bullock Double Panniers (Pothi-Maadu) & Brass Litre Measures",
        "name_ta": "மலைக்கூடை மூங்கில் கொட்டான்கள், பொதிமாட்டு இரட்டைச் சாக்குகள் மற்றும் பித்தளைப் படி அளவைகள்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 1950,
        "thinai": "kurinji",
        "summary_en": "Material equipment of the Western Ghats cardamom harvest and ghat caravan trade: waist-slung woven bamboo picking baskets (koodai), moisture-proofwaxed gunny and palmyra-mat double saddlebags (pothi) carried by hill pack-bullocks, and brass volume gauges.",
        "summary_ta": "ஏலக்காய் அறுவடை மற்றும் மலைப் பாதை வணிகக் கருவிகள்: இடுப்பில் கட்டும் மூங்கில் கொட்டான் கூடைகள், மலைப் பாதைகளில் பொதிமாடுகள் சுமக்கும் இரட்டைப் பொதிப் பைகள் மற்றும் பித்தளை அளவைப் படிகள்.",
        "sources": [
            "Madurai District Manual (Ghat Passes & Pack-Bullock Trade)",
            "Periyakulam and Bodinayakanur Caravan Oral Histories",
            "Ethnographic Artifacts of the Western Ghats"
        ],
        "content": "# Bamboo Picking Baskets, Pothi-Maadu Panniers & Brass Measures\n\nTransporting delicate, moisture-sensitive cardamom capsules down precipitous mountain trails (*kombu-vazhi*) from the high ranges to the plains markets of Tamil Nadu required specialized gear:\n\n**Harvest & Caravan Toolkit:**\n- **Waist-Slung Bamboo *Kottan* / *Koodai***: Pickers weave tight, narrow-mouthed split-bamboo baskets strapped to the waist or slung across the forehead so both hands remain free to part the leafy pseudostems and snip basal panicle pods without bruising them.\n- **Pothi-Maadu Double Saddlebags**: Before motorable ghat roads, trains of agile hill pack-bullocks (*pothi-maadu*) descended stone-paved bridle paths carrying balanced twin panniers (*pothi*). Cured cardamom was double-wrapped in dried plantain/palmyra inner mats and thick hemp gunny sacks to prevent mountain mist from re-wetting the pods (which triggers mould and bleaches the green coat).\n- **Brass *Padi* & Balance Beams**: Downhill *pettai* warehouses used calibrated cylindrical brass *padi* measures and *thulakkol* steelyards to test bulk density and net weight upon arrival."
    },
    {
        "slug": "concept-eladhi-chooranam-siddha-pharmacology-and-tridosha-digestive-therapeutics",
        "category": "concept",
        "file": "concept-eladhi-chooranam-siddha-pharmacology-and-tridosha-digestive-therapeutics.md",
        "name_en": "Eladhi Chooranam in Siddha Medicine: Pitta-Cooling, Carminative & Respiratory Pharmacology",
        "name_ta": "சித்த மருத்துவத்தில் ஏலாதி சூரணம்: பித்த சமனம், செரிமானத் தூண்டல் மற்றும் சுவாச நோய் நீக்கும் மருத்துவ குணம்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Classical Tamil medical and ethical traditions surrounding cardamom: from the Pathinenkilkanakku didactic work Eladhi ( comparing six moral truths to a six-ingredient cardamom electuary) to Siddha formulations like Eladhi Chooranam for excess Pitta, nausea, halitosis, and bronchial phlegm.",
        "summary_ta": "திருக்குறள் சார்ந்த பதினெண்கீழ்க்கணக்கு நூலான 'ஏலாதி' தொடங்கி சித்த மருத்துவத்தின் 'ஏலாதி சூரணம்' வரை ஏலக்காயின் மருத்துவப் பயன்கள்: பித்த வாந்தி, அजीரணம், வாய் நாற்றம் மற்றும் கப நோய் நீக்கும் மருந்தியல்.",
        "sources": [
            "Eladhi (Kanimedhaviyar, Pathinenkilkanakku)",
            "Agathiyar Gunavagadam",
            "Siddha Formulary of India (Eladhi Chooranam)"
        ],
        "content": "# Eladhi Chooranam & Siddha Pharmacology of Cardamom\n\nIn Tamil literary and medical history, cardamom lends its name both to a classical ethical treatise (*Eladhi* in the *Pathinenkilkanakku* anthology) and to a cornerstone polyherbal formula in Siddha medicine:\n\n**Literary & Medical Doctrine:**\n- **The Classical *Eladhi* Six-Spice Formula**: Compiled by Kanimedhaviyar, the poem *Eladhi* takes its title from a revered six-ingredient medicinal compound led by cardamom (*elam*,one part), combined in ascending proportions with cinnamon bark (*lavangappattai*), *nagakesara* stamens (*sirunagappoo*), black pepper (*milagu*), *vishnukranthi*, and dry ginger (*sukku*).\n- **Gunavagadam Humoral Action**: In Siddha *Gunavagadam* materia medica, *Ela-arisi* possesses a pungent-sweet (*karppu-inippu*) taste, cooling potency (*seethala veeriyam*), and sweet post-digestive effect.\n- **Clinical Indications (*Eladhi Chooranam*)**: Finely ground decorticated cardamom seeds compounded with cloves, *javathu*/sandal, and sugar cane candy pacify aggravated *Pitta* (biliousness, burning gastritis, vertigo, and morning nausea), stimulate digestive fire (*anal*), clear throat phlegm (*kapham*), and sweeten the breath."
    },
    {
        "slug": "institution-kuravar-hill-spice-gatherers-and-ghat-pettai-caravan-guilds",
        "category": "institution",
        "file": "institution-kuravar-hill-spice-gatherers-and-ghat-pettai-caravan-guilds.md",
        "name_en": "Kunra-Kuravar Hill Gatherers, Palaiyakkaran Forest Leases & Pettai Spice Caravan Guilds",
        "name_ta": "குன்றக் குறவர் மலைச் சேகரிப்பாளர்கள், பாளையக்காரர் காட்டுக் குத்தகை மற்றும் பேட்டை ஏல வணிகக் குழுக்கள்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 1950,
        "thinai": "kurinji",
        "summary_en": "Socio-economic organization of the Western Ghats cardamom trade: indigenous Kuravar and Mannan hill foragers maintaining wild forest clumps, Nayak/Palaiyakkaran forest collection tenures, and lowland Pettai merchant-banker guilds financing pack-bullock ghat caravans.",
        "summary_ta": "மேற்குத் தொடர்ச்சி மலை ஏலக்காய் வணிக அமைப்பு: காட்டு ஏலத்தைக் காத்து அறுவடை செய்த குன்றக் குறவர் மற்றும் மன்னான் பழங்குடியினர், பாளையக்காரர் மலைக் குத்தகை மற்றும் அடிவாரப் பேட்டை வணிகர் சங்கங்கள்.",
        "sources": [
            "Malaipadukadam",
            "Madurai Country and Bodinayakanur Zamindari Records",
            "Travancore Cardamom Monopoly & Hill Tribe Histories"
        ],
        "content": "# Kuravar Hill Spice Gatherers & Ghat Pettai Caravan Guilds\n\nFor over two millennia, the flow of green cardamom from high-altitude shola forests to coastal ports and temple towns relied on a specialized network linking indigenous forest stewards with lowland merchant guilds:\n\n**Institutional Architecture:**\n- **Indigenous Shola Stewardship (*Kunra-Kuravar* & *Mannan*)**: Forest-dwelling *Kuravar*, *Mannan*, and *Paliyar* communities practiced rotational canopy-gap clearing (*kattu-vettu*): felling a single senescent forest giant to admit dappled light over dormant wild cardamom rhizomes in the soil bank, triggering vigorous fruiting for 10–12 years before allowing the forest to regenerate.\n- **Barter & *Thavalam* Foot-Markets**: Hill gatherers carried cured pods down to foothill exchange posts (*thavalam* and *pettai*), trading cardamom, wild honey, wax, and dammar resin for coastal sea-salt, dried fish, iron billhooks, and cotton cloth.\n- **Pettai Merchant Guilds & Caravan Financing**: In foothill market towns like Bodinayakanur, Cumbum, and Periyakulam, merchant guilds (*Chettis* and *Nattukottai/Vellan* traders) operated bonded curing warehouses, graded bulk lots, and dispatched armed pack-bullock caravans eastward to Madurai and westward toward Cochin and Alleppey."
    },
    {
        "slug": "place-bodinayakanur-ancient-cardamom-hills-and-kurinji-spice-haven",
        "category": "place",
        "file": "place-bodinayakanur-ancient-cardamom-hills-and-kurinji-spice-haven.md",
        "name_en": "Bodinayakanur: Ancient Cardamom Hills Gateway, Ghat Pass & Kurinji Spice Capital",
        "name_ta": "போடிநாயக்கனூர் - பண்டைய ஏலமலைக் கணவாய், குறிஞ்சி நறுமணப் பொருள் சந்தை மற்றும் ஏலக்காய் நகரம்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Historic foothill market town at the eastern base of the Cardamom Hills (Elamalai) in Theni district (10.0100° N, 77.3500° E), commanding the Bodimettu and Kottagudi mountain passes where high-range Kurinji cardamom converges for curing, grading, and national auction.",
        "summary_ta": "தேனி மாவட்டத்தில் மேற்குத் தொடர்ச்சி மலையின் ஏலமலை அடிவாரத்தில் அமைந்துள்ள போடிநாயக்கனூர் (10.0100° N, 77.3500° E): போடிமெட்டு மற்றும் கொட்டக்குடி மலைக் கணவாய்கள் வழியாக வரும் ஏலக்காயைப் பதப்படுத்தித் தரம் பிரிக்கும் வரலாற்றுச் சந்தை.",
        "sources": [
            "Madurai District Gazetteer (Bodinayakanur & Cardamom Hills)",
            "Theni District Historical & Agricultural Records",
            "South Indian Spice Route Geography"
        ],
        "content": "# Bodinayakanur: Ancient Cardamom Hills Gateway & Kurinji Spice Haven\n\nSituated at the dramatic eastern escarpment of the Western Ghats in the Suruli–Kottagudi river basin of Theni district (10.0100° N, 77.3500° E), Bodinayakanur stands at the foot of the **Cardamom Hills (*Elamalai*)** as India's historic \"Cardamom Capital\":\n\n**Geographic & Commercial Significance:**\n- **Commanding the Ghat Passes (*Bodimettu* & *Top Station*)**: Steep ancient pack-trails (*kombu-vazhi*) descending from the 1,400-metre shola plateaus of Munnar, Devikulam, Udumbanchola, and Agamalai funnel directly into the Kottagudi valley at Bodinayakanur.\n- **Microclimate Advantage for Curing & Storage**: While the upper high-range rainforests remain saturated in monsoon cloud and mist, the rain-shadow valley floor at Bodinayakanur offers dry, warm air ideal for final moisture conditioning, sulphur-free sorting, and long-term warehousing without fungal spoilage.\n- **Generational Grading & Trade Ecosystem**: Thousands of women spice-graders (*podi-peigal*), kiln curers, and spice brokers in Bodinayakanur sort Western Ghats harvests by sieve size and litre-weight before dispatching aromatic consignments across India and overseas."
    }
]

EDGES = [
    [
        "text-sangam-and-silappadikaram-on-elam-cardamom-and-kurinji-forest-aromatics",
        "describes",
        "concept-elettaria-cardamomum-understory-shade-ecology-and-terpinyl-acetate-chemistry",
        "material_culture",
        "Sangam to Post-Sangam Era",
        "Malaipadukadam, Kurinjippattu, and Silappadikaram document the shaded montane forest ecology and fragrant produce of Western Ghats cardamom.",
        "Malaipadukadam & Silappadikaram"
    ],
    [
        "concept-elettaria-cardamomum-understory-shade-ecology-and-terpinyl-acetate-chemistry",
        "governs",
        "technology-basal-panicle-selective-picking-and-alkaline-ash-chlorophyll-washing",
        "material_culture",
        "Medieval to Modern Era",
        "Sequential flowering along basal panicles and delicate epicarp chlorophyll chemistry necessitate selective karukkai hand-picking and alkaline washing.",
        "Cardamom Research Monographs"
    ],
    [
        "technology-basal-panicle-selective-picking-and-alkaline-ash-chlorophyll-washing",
        "feeds",
        "technology-odai-flue-kiln-thermal-curing-and-coir-mat-chaff-winnowing",
        "material_culture",
        "Medieval to Modern Era",
        "Alkali-washed karukkai green capsules are immediately transferred to indirect wood-flue odai kilns for controlled dehydration.",
        "Post-Harvest Spice Guides"
    ],
    [
        "technology-odai-flue-kiln-thermal-curing-and-coir-mat-chaff-winnowing",
        "produces",
        "artifact-bold-alappey-green-cardamom-pods-and-aromatic-seed-essential-oils",
        "material_culture",
        "Medieval to Modern Era",
        "Stepped thermal curing below 55°C and coir-mat calyx rubbing yield parrot-green three-valved cardamom capsules rich in volatile oil.",
        "Bodinayakanur Curing Records"
    ],
    [
        "concept-karukkai-pazhakai-capsule-ripeness-chlorophyll-retention-and-grading-metrics",
        "classifies",
        "artifact-bold-alappey-green-cardamom-pods-and-aromatic-seed-essential-oils",
        "material_culture",
        "Medieval to Modern Era",
        "Litre-weight bulk density and perforated brass sieve gauges classify cured green cardamom pods into Extra Bold, Bold, and Split grades.",
        "Agmark Grading Standards"
    ],
    [
        "artifact-bold-alappey-green-cardamom-pods-and-aromatic-seed-essential-oils",
        "compounds",
        "concept-eladhi-chooranam-siddha-pharmacology-and-tridosha-digestive-therapeutics",
        "material_culture",
        "Sangam to Modern Era",
        "Decorticated Ela-arisi seeds from cured pods form the primary active ingredient in classical Eladhi ethical-medical formulas and Siddha Eladhi Chooranam.",
        "Eladhi & Agathiyar Gunavagadam"
    ],
    [
        "institution-kuravar-hill-spice-gatherers-and-ghat-pettai-caravan-guilds",
        "employs",
        "artifact-kombu-vazhi-pack-bullock-panniers-and-bamboo-picking-baskets",
        "material_culture",
        "Sangam to Modern Era",
        "Hill pickers and Pettai caravan drivers used waist-slung bamboo baskets and double-wrapped pothi-maadu pack-bullock panniers across mountain trails.",
        "Madurai District Manual"
    ],
    [
        "artifact-kombu-vazhi-pack-bullock-panniers-and-bamboo-picking-baskets",
        "transports",
        "artifact-bold-alappey-green-cardamom-pods-and-aromatic-seed-essential-oils",
        "material_culture",
        "Sangam to Modern Era",
        "Moisture-proofed pothi-maadu saddlebags protected kiln-cured green cardamom capsules from mountain mist along steep ghat trails.",
        "Caravan Oral Histories"
    ],
    [
        "institution-kuravar-hill-spice-gatherers-and-ghat-pettai-caravan-guilds",
        "operates_in",
        "place-bodinayakanur-ancient-cardamom-hills-and-kurinji-spice-haven",
        "material_culture",
        "Sangam to Modern Era",
        "Kurinji hill gatherers and lowland spice-market guilds converged at the Bodimettu and Kottagudi ghat passes in Bodinayakanur.",
        "Madurai District Gazetteer"
    ],
    [
        "text-sangam-and-silappadikaram-on-elam-cardamom-and-kurinji-forest-aromatics",
        "celebrates",
        "place-bodinayakanur-ancient-cardamom-hills-and-kurinji-spice-haven",
        "material_culture",
        "Sangam to Modern Era",
        "The classical Kurinji spice hills celebrated in Sangam poetry find their premier commercial gateway at Bodinayakanur at the foot of Elamalai.",
        "Kurinjippattu & Theni Records"
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
