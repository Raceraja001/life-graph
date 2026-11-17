#!/usr/bin/env python3
"""
Harvester: Batch 56 - Ancient Tamil Tamarind (Puli) Agroforestry & Tartaric Acid Technology
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
    "slug": "technology-puli-pod-harvesting-deseeding-rock-salt-compacting-and-mattai-puli-maturation-technology",
    "file": "technology-puli-pod-harvesting-deseeding-rock-salt-compacting-and-mattai-puli-maturation-technology.md",
    "category": "technology",
    "name_en": "Puli Pod Harvesting, Deseeding, Rock-Salt Compacting & Mattai-Puli Maturation Technology",
    "name_ta": "புளி நெற்று அறுவடை, கொட்டை நீக்குதல், கல் உப்புப் பிசைவு மற்றும் மட்டைப் புளி பதப்படுத்தும் தொழில்நுட்பம்",
    "era": "Sangam Era to Modern Era",
    "year_start": -300,
    "year_end": 2026,
    "thinai": "mullai",
    "summary_en": "The traditional post-harvest processing of Tamarindus indica pods in Tamil agro-ecosystems: shaking ripe branches with hooked bamboo poles (thotti-kombu), cracking brittle dry brittle shells, removing fibrous veins and stony seeds (puliyaankottai), layering the sticky pulp with coarse sea salt (kal uppu), and trampling or pounding into dense rectangular cakes (mattai puli) cured in glazed ceramic bharani jars for multi-year stability.",
    "summary_ta": "தமிழ் உழவியல் மரபில் புளியங்காய் பதப்படுத்துதல்: தோட்டிக் கொம்பு கொண்டு பழுத்த நெற்றுகளை உலுக்கிப் பறித்தல், மேலோட்டை உடைத்து நார் மற்றும் கொட்டைகளை நீக்குதல், கல் உப்புடன் சேர்த்துப் பிசைந்து அடர்த்தியான மட்டைப் புளியாக உருட்டி மண்பாண்டப் பரணிகளில் பல்லாண்டுகள் கெடாமல் பாதுகாக்கும் தொழில்நுட்பம்.",
    "sources": [
      "Perumpanarruppadai 95-105",
      "Malaipadukadam 420-435",
      "Tamil Agro-Forestry Traditional Knowledge Registers"
    ],
    "content": "---\nslug: technology-puli-pod-harvesting-deseeding-rock-salt-compacting-and-mattai-puli-maturation-technology\ncategory: technology\nname_en: Puli Pod Harvesting, Deseeding, Rock-Salt Compacting & Mattai-Puli Maturation Technology\nname_ta: புளி நெற்று அறுவடை, கொட்டை நீக்குதல், கல் உப்புப் பிசைவு மற்றும் மட்டைப் புளி பதப்படுத்தும் தொழில்நுட்பம்\nera: Sangam Era to Modern Era\nyear_start: -300\nyear_end: 2026\nthinai: mullai\nsummary_en: The traditional post-harvest processing of Tamarindus indica pods in Tamil agro-ecosystems: shaking ripe branches with hooked bamboo poles (thotti-kombu), cracking brittle dry brittle shells, removing fibrous veins and stony seeds (puliyaankottai), layering the sticky pulp with coarse sea salt (kal uppu), and trampling or pounding into dense rectangular cakes (mattai puli) cured in glazed ceramic bharani jars for multi-year stability.\nsummary_ta: தமிழ் உழவியல் மரபில் புளியங்காய் பதப்படுத்துதல்: தோட்டிக் கொம்பு கொண்டு பழுத்த நெற்றுகளை உலுக்கிப் பறித்தல், மேலோட்டை உடைத்து நார் மற்றும் கொட்டைகளை நீக்குதல், கல் உப்புடன் சேர்த்துப் பிசைந்து அடர்த்தியான மட்டைப் புளியாக உருட்டி மண்பாண்டப் பரணிகளில் பல்லாண்டுகள் கெடாமல் பாதுகாக்கும் தொழில்நுட்பம்.\nsources:\n  - Perumpanarruppadai 95-105\n  - Malaipadukadam 420-435\n  - Tamil Agro-Forestry Traditional Knowledge Registers\n---\n\n# Puli Pod Harvesting, Deseeding, Rock-Salt Compacting & Mattai-Puli Maturation Technology\n\nTamarind (**Tamarindus indica**, Tamil: **புளி / Puli**, anciently **திதலைப்புளி / Thithalaip-puli**) constitutes the structural souring backbone and domestic preservative pillar of Tamil cuisine and metallurgy.\n\n### 1. Seasonal Shaking & Pole Harvesting (*நெற்று உலுக்கல்*)\n- Pods mature during the dry hot months (February to April). Harvesting is timed when the outer epicarp turns cinnamon-brown and rattles lightly when tapped.\n- Harvesters climb massive branching trees armed with long split-bamboo poles tipped with iron hooks (*thotti-kombu* / தோட்டி கொம்பு) to shake high fruiting limbs, allowing pods to drop onto cleared ground.\n\n### 2. De-shelling & De-seeding (*ஓடு உடைத்தல் மற்றும் கொட்டை நீக்கல்*)\n- The brittle shell (*odu*) is cracked between fingers or tapped lightly with small wooden mallets.\n- The sticky reddish-brown mesocarp pulp is stripped of longitudinal fibrous strings (*puli-naar*).\n- Stony endocarp seeds (*puliyaankottai*) are popped out using blunt copper scrapers or hand pressing. Retaining seeds invites moisture and weevil infestation (*bruchid beetles*), whereas seedless pulp can endure for years.\n\n### 3. Rock-Salt Compacting & Mattai-Puli Processing (*மட்டைப் புளி*)\n- Seedless pulp is spread under intense sun on palm mats for 2 to 3 days to lower water activity below 0.6.\n- It is then kneaded with 8 to 10 percent unrefined sea salt (*kal uppu* / கல் உப்பு) and a trace of sesame oil.\n- The salted pulp is tightly packed and rammed into dense earthen urns or compressed into rectangular blocks wrapped in dried palmyra leaf sheaths (*mattai*).\n- Under anaerobic storage, the pulp undergoes slow dark caramelization—turning from amber to glossy black—developing deep umami complexity known as aged vintage tamarind (*pazham-puli* / பழம்புளி).\n"
  },
  {
    "slug": "technology-puli-ittu-vilakki-tartaric-acid-chelation-brass-bronze-cleaning-and-culinary-acid-stewing-technology",
    "file": "technology-puli-ittu-vilakki-tartaric-acid-chelation-brass-bronze-cleaning-and-culinary-acid-stewing-technology.md",
    "category": "technology",
    "name_en": "Puli-Ittu-Vilakki Tartaric Acid Chelation, Brass-Bronze Cleaning & Culinary Acid Stewing Technology",
    "name_ta": "புளி இட்டு விளக்குதல், டார்டாரிக் அமில உலோகத் தூய்மைப்படுத்தல் மற்றும் சமையல் புளிக்குழம்புத் தொழில்நுட்பம்",
    "era": "Sangam Era to Modern Era",
    "year_start": -300,
    "year_end": 2026,
    "thinai": "marutham",
    "summary_en": "Dual physicochemical applications of tamarind pulp: scouring tarnished bronze, bell-metal, and brass lamps/idols using tamarind paste and wood ash where tartaric acid chelates cuprous/cupric oxides into soluble copper tartrate complexes (puli-ittu-vilakki), alongside culinary stewing kinetics where boiling tamarind water tenderizes collagen-rich fish and meat fibers while preventing microbiological spoilage.",
    "summary_ta": "புளியின் இரட்டை வேதியியல் பயன்முறை: பித்தளை, வெண்கல விளக்குகள் மற்றும் சிலைகளில் படரும் தாமிர ஆக்சைடுகளை டார்டாரிக் அமிலக் கரைசல் கொண்டு நீக்கிப் பளபளப்பாக்கும் 'புளி இட்டு விளக்குதல்' மற்றும் இறைச்சி, மீன் தசை நார்களை மெதுவாக்கிக் கெடாமல் காக்கும் புளிக்குழம்புச் சமையல் தொழில்நுட்பம்.",
    "sources": [
      "Silappadikaram: Adaikkala Kaathai",
      "Thirumandiram Tantra 3",
      "Corrosion Science: Organic Acid Metal Cleaning"
    ],
    "content": "---\nslug: technology-puli-ittu-vilakki-tartaric-acid-chelation-brass-bronze-cleaning-and-culinary-acid-stewing-technology\ncategory: technology\nname_en: Puli-Ittu-Vilakki Tartaric Acid Chelation, Brass-Bronze Cleaning & Culinary Acid Stewing Technology\nname_ta: புளி இட்டு விளக்குதல், டார்டாரிக் அமில உலோகத் தூய்மைப்படுத்தல் மற்றும் சமையல் புளிக்குழம்புத் தொழில்நுட்பம்\nera: Sangam Era to Modern Era\nyear_start: -300\nyear_end: 2026\nthinai: marutham\nsummary_en: Dual physicochemical applications of tamarind pulp: scouring tarnished bronze, bell-metal, and brass lamps/idols using tamarind paste and wood ash where tartaric acid chelates cuprous/cupric oxides into soluble copper tartrate complexes (puli-ittu-vilakki), alongside culinary stewing kinetics where boiling tamarind water tenderizes collagen-rich fish and meat fibers while preventing microbiological spoilage.\nsummary_ta: புளியின் இரட்டை வேதியியல் பயன்முறை: பித்தளை, வெண்கல விளக்குகள் மற்றும் சிலைகளில் படரும் தாமிர ஆக்சைடுகளை டார்டாரிக் அமிலக் கரைசல் கொண்டு நீக்கிப் பளபளப்பாக்கும் 'புளி இட்டு விளக்குதல்' மற்றும் இறைச்சி, மீன் தசை நார்களை மெதுவாக்கிக் கெடாமல் காக்கும் புளிக்குழம்புச் சமையல் தொழில்நுட்பம்.\nsources:\n  - Silappadikaram: Adaikkala Kaathai\n  - Thirumandiram Tantra 3\n  - Corrosion Science: Organic Acid Metal Cleaning\n---\n\n# Puli-Ittu-Vilakki Tartaric Acid Chelation, Brass-Bronze Cleaning & Culinary Acid Stewing Technology\n\nThe phrase **\"புளி இட்டு விளக்குதல்\" (Puli-Ittu-Vilakki)** is both a staple household ritual and a Tamil idiomatic proverb for rigorous purification.\n\n### 1. Metallurgical Chelation Mechanics (*உலோகத் தூய்மைப்படுத்தல்*)\n- Bronze (*vengalam*), brass (*pithalai*), and copper (*chembu*) vessels exposed to air develop dull coatings of basic copper carbonate (verdigris / *thambu* / தம்பு) and cupric oxides (CuO, Cu2O).\n- Tamarind pulp contains 8 to 12 percent **L(+)-tartaric acid** alongside malic and citric acids:\n  - When tamarind pulp is rubbed across tarnished metal with salt and rice husk ash (*umi sambal*), tartaric acid dissociates, donating carboxylate protons that dissolve insoluble copper oxides into soluble **copper tartrate chelate complexes**:\n    $$\text{CuO} + \text{H}_2\text{C}_4\text{H}_4\text{O}_6 \rightarrow \text{Cu(C}_4\text{H}_4\text{O}_6) + \text{H}_2\text{O}$$\n  - The chloride ions from sea salt accelerate dissolution of passive oxide films, while ash acts as a micro-abrasive. Rinsing in cold water reveals lustrous, mirror-bright copper-tin alloy surfaces.\n\n### 2. Culinary Stewing & Acid Denaturation (*புளிக்குழம்பு வேதியியல்*)\n- In Tamil cuisine (*Puli Kuzhambu*, *Meen Kuzhambu*, *Vatha Kuzhambu*), tamarind extract is heated in earthen pots (*kalchatti* or *manchatti*):\n  - At pH 3.0 to 3.5, tartaric acid protonates myofibrillar proteins and denatures fibrous connective tissue (collagen), rendering tough meats and fish tender within minutes.\n  - The low pH environment suppresses proliferation of spore-forming food-poisoning microbes (*Clostridium*, *Bacillus*), permitting curries to remain edible without sour spoilage for up to 72 hours under tropical ambient temperatures.\n"
  },
  {
    "slug": "artifact-salted-mattai-puli-earthenware-bharani-wooden-pod-mallets-and-bronze-kinnam-pots",
    "file": "artifact-salted-mattai-puli-earthenware-bharani-wooden-pod-mallets-and-bronze-kinnam-pots.md",
    "category": "artifact",
    "name_en": "Salted Mattai-Puli, Earthenware Bharani, Wooden Pod Mallets & Bronze Kinnam Pots",
    "name_ta": "கல் உப்பு மட்டைப் புளி, மண்பாண்டப் பரணிகள், புளி உடைக்கும் மரக் கொட்டணிகள் மற்றும் வெண்கலக் கிண்ணங்கள்",
    "era": "Medieval Chola to Modern Era",
    "year_start": 900,
    "year_end": 2026,
    "thinai": "marutham",
    "summary_en": "The physical artifacts of Tamil tamarind conservation: dense pressed cakes of salted black tamarind wrapped in palmyra leaf sheaths (mattai puli), glazed stoneware storage jars (bharani) with tight earthen lids, hardwood pestles used to crack brittle pods, and heavy bronze bowls (kinnam) polished to golden luster with tamarind water.",
    "summary_ta": "தமிழ் புளிப் பயன்பாட்டின் தொல்பொருட்கள்: பனையோலை மட்டையில் பொதிந்த கல் உப்பு மட்டைப் புளிக் கட்டிகள், சுடுமண் பரணிப் பானைகள், புளி உடைக்கப் பயன்படும் மரக் கொட்டணிகள் மற்றும் புளித்தண்ணீர் கொண்டு விளக்கப்பட்ட பொன்னிற வெண்கலக் கிண்ணங்கள்.",
    "sources": [
      "Thanjavur Brihadisvara Temple Storehouse Inscriptions",
      "Madurai Nayaka Domestic Kitchen Inventories",
      "Tamil Nadu Folklore Artifact Survey"
    ],
    "content": "---\nslug: artifact-salted-mattai-puli-earthenware-bharani-wooden-pod-mallets-and-bronze-kinnam-pots\ncategory: artifact\nname_en: Salted Mattai-Puli, Earthenware Bharani, Wooden Pod Mallets & Bronze Kinnam Pots\nname_ta: கல் உப்பு மட்டைப் புளி, மண்பாண்டப் பரணிகள், புளி உடைக்கும் மரக் கொட்டணிகள் மற்றும் வெண்கலக் கிண்ணங்கள்\nera: Medieval Chola to Modern Era\nyear_start: 900\nyear_end: 2026\nthinai: marutham\nsummary_en: The physical artifacts of Tamil tamarind conservation: dense pressed cakes of salted black tamarind wrapped in palmyra leaf sheaths (mattai puli), glazed stoneware storage jars (bharani) with tight earthen lids, hardwood pestles used to crack brittle pods, and heavy bronze bowls (kinnam) polished to golden luster with tamarind water.\nsummary_ta: தமிழ் புளிப் பயன்பாட்டின் தொல்பொருட்கள்: பனையோலை மட்டையில் பொதிந்த கல் உப்பு மட்டைப் புளிக் கட்டிகள், சுடுமண் பரணிப் பானைகள், புளி உடைக்கப் பயன்படும் மரக் கொட்டணிகள் மற்றும் புளித்தண்ணீர் கொண்டு விளக்கப்பட்ட பொன்னிற வெண்கலக் கிண்ணங்கள்.\nsources:\n  - Thanjavur Brihadisvara Temple Storehouse Inscriptions\n  - Madurai Nayaka Domestic Kitchen Inventories\n  - Tamil Nadu Folklore Artifact Survey\n---\n\n# Salted Mattai-Puli, Earthenware Bharani, Wooden Pod Mallets & Bronze Kinnam Pots\n\nEvery traditional Tamil kitchen (*samayal-arai*) and temple storehouse (*madapalli*) maintained an armada of dedicated vessels for tamarind curation.\n\n### 1. Pressed Mattai-Puli Cakes (*மட்டைப் புளி*)\n- Dried, deseeded tamarind kneaded with sea salt was compressed into thick bricks and wrapped tightly in outer palmyra leaf sheaths (*panang-mattai*) tied with coir twine.\n- These dense blocks prevented interior air penetration, inhibiting oxidative discoloration and mould growth while retaining the moist, resinous consistency of aged tartaric paste.\n\n### 2. Glazed Ceramic Bharani (*பீங்கான் / மண்பாண்டப் பரணி*)\n- Because tartaric acid vigorously corrodes iron, copper, and tin, raw tamarind was never kept in metal vessels.\n- Storage was exclusively relegated to salt-glazed earthenware urns or vitrified stoneware jars (*bharani*). The non-reactive ceramic glaze resisted organic acid etching, maintaining pristine storage integrity for decades.\n\n### 3. Wooden De-Shelling Mallets & Bronze Kinnam\n- Small mallets carved from babool (*karuvelam*) or tamarind heartwood were used on threshold stones to tap dry pods without pulverizing the sticky interior flesh.\n- Deep bronze food bowls (*kinnam* and *gopuram-uruLi*) cleaned weekly with tamarind paste acquired a rich burnished gold patina, celebrated in temple banqueting halls.\n"
  },
  {
    "slug": "artifact-tamarind-wood-mortar-pestles-charcoal-braziers-and-puli-kuzhambu-clay-chatti-cookware",
    "file": "artifact-tamarind-wood-mortar-pestles-charcoal-braziers-and-puli-kuzhambu-clay-chatti-cookware.md",
    "category": "artifact",
    "name_en": "Tamarind-Wood Mortar Pestles, Charcoal Braziers & Puli-Kuzhambu Clay Chatti Cookware",
    "name_ta": "புளியமர உலக்கைகள், மரக்கரி அடுப்புகள் மற்றும் புளிக்குழம்பு சுடுமண் சட்டிப் பாண்டங்கள்",
    "era": "Medieval to Modern Era",
    "year_start": 800,
    "year_end": 2026,
    "thinai": "mullai",
    "summary_en": "Culinary artifacts utilizing the timber and chemistry of the tamarind tree: dense, interlocked-grain tamarind heartwood chopping blocks and grain pounding pestles (ulakkai), slow-burning hardwood charcoal braziers, and seasoned porous clay stewing pots (meen chatti) that absorb spice oils and buffer acid heat.",
    "summary_ta": "புளியமர மரக்கட்டை மற்றும் சுடுமண் சார்ந்த சமையற்கருவிகள்: நெளிந்த நார் அமைப்பு கொண்ட புளியமர உரல்-உலக்கைகள் மற்றும் இறைச்சி வெட்டும் கட்டைகள், புளியமரக் கரி அடுப்புகள் மற்றும் எண்ணெய் பிசுக்கு பளபளக்கும் புளிக்குழம்பு மண் சட்டிகள்.",
    "sources": [
      "Purananuru 29",
      "South Indian Timber Technology Studies",
      "Traditional Tamil Kitchen Material Culture"
    ],
    "content": "---\nslug: artifact-tamarind-wood-mortar-pestles-charcoal-braziers-and-puli-kuzhambu-clay-chatti-cookware\ncategory: artifact\nname_en: Tamarind-Wood Mortar Pestles, Charcoal Braziers & Puli-Kuzhambu Clay Chatti Cookware\nname_ta: புளியமர உலக்கைகள், மரக்கரி அடுப்புகள் மற்றும் புளிக்குழம்பு சுடுமண் சட்டிப் பாண்டங்கள்\nera: Medieval to Modern Era\nyear_start: 800\nyear_end: 2026\nthinai: mullai\nsummary_en: Culinary artifacts utilizing the timber and chemistry of the tamarind tree: dense, interlocked-grain tamarind heartwood chopping blocks and grain pounding pestles (ulakkai), slow-burning hardwood charcoal braziers, and seasoned porous clay stewing pots (meen chatti) that absorb spice oils and buffer acid heat.\nsummary_ta: புளியமர மரக்கட்டை மற்றும் சுடுமண் சார்ந்த சமையற்கருவிகள்: நெளிந்த நார் அமைப்பு கொண்ட புளியமர உரல்-உலக்கைகள் மற்றும் இறைச்சி வெட்டும் கட்டைகள், புளியமரக் கரி அடுப்புகள் மற்றும் எண்ணெய் பிசுக்கு பளபளக்கும் புளிக்குழம்பு மண் சட்டிகள்.\nsources:\n  - Purananuru 29\n  - South Indian Timber Technology Studies\n  - Traditional Tamil Kitchen Material Culture\n---\n\n# Tamarind-Wood Mortar Pestles, Charcoal Braziers & Puli-Kuzhambu Clay Chatti Cookware\n\nThe tamarind tree (*Tamarindus indica*) is prized not only for its fruit pulp but equally for its exceedingly tough, interlocked heartwood and fuel properties.\n\n### 1. Interlocked Tamarind Heartwood Implements (*புளியமர உலக்கை*)\n- Tamarind heartwood is dark purplish-brown, extremely hard, heavy (air-dry density > 900 kg/m³), and possesses heavily twisted, interlocked grain that resists splitting under heavy vertical impact.\n- Traditional carpenters fashioned heavy paddy pounding pestles (*ulakkai*), oil-press pestles (*chekku-ural*), and butcher chopping blocks (*vettu-kattai*) from aged tamarind trunks. Unlike softer woods, it does not splinter into food fibers during vigorous pounding.\n\n### 2. High-Calorific Hardwood Charcoal (*புளியமரக் கரி*)\n- Tamarind branchwood yields dense, slow-burning charcoal with high calorific value and minimal spark ejection.\n- Blacksmiths and bronzesmiths (*Kammalar*) prized tamarind charcoal for heating crucible furnaces, while domestic kitchens used charcoal embers inside clay braziers (*kumutti*) to gently simmer tamarind stews overnight.\n\n### 3. Seasoned Porous Manchatti Cookware (*புளிக்குழம்பு மண் சட்டி*)\n- The porous micaceous terracotta stewing bowl (*manchatti*) is the premier vessel for cooking tamarind-rich gravies (*puli-kuzhambu* and *meen-kuzhambu*).\n- Heated over gentle wood fires, the clay walls gently radiate alkaline minerals that buffer harsh acid peaks while locking in fragrant volatile oils (mustard, fenugreek, curry leaves), creating a rounded savoury taste profile impossible to achieve in steel pans.\n"
  },
  {
    "slug": "concept-tartaric-acid-isomer-chelation-chemistry-copper-oxide-dissolution-and-food-preservation",
    "file": "concept-tartaric-acid-isomer-chelation-chemistry-copper-oxide-dissolution-and-food-preservation.md",
    "category": "concept",
    "name_en": "Tartaric Acid Isomer Chelation Chemistry, Copper Oxide Dissolution & Food Preservation",
    "name_ta": "டார்டாரிக் அமில வேதியியல், தாமிர ஆக்சைடு கரைப்பு மற்றும் உணவுப் பாதுகாப்பு அறிவியல்",
    "era": "Sangam Era to Modern Era",
    "year_start": -300,
    "year_end": 2026,
    "thinai": "marutham",
    "summary_en": "The molecular science of Tamarindus indica acidity: high concentrations of natural L(+)-tartaric acid (2,3-dihydroxybutanedioic acid) resisting bacterial degradation, dicarboxylic bidentate chelation bonding with copper and iron cations, lowering of food water activity (aw), and thermal stability up to 175°C preventing loss of sourness during prolonged boiling.",
    "summary_ta": "புளியின் அமில வேதியியல்: அதிக அளவில் காணப்படும் L(+)-டார்டாரிக் அமிலம், தாமிர மற்றும் இரும்பு அயனிகளுடன் பிணைந்து கறைகளை நீக்கும் 'செலேஷன்' வேதிவினை, பாக்டீரியா வளர்ச்சியைத் தடுக்கும் குறைந்த கார-அமில நிலை (pH 2.8-3.2) மற்றும் 175 பாகை வரை சுவை மாறாமல் கொதிக்கும் வெப்ப நிலைப்புத்தன்மை.",
    "sources": [
      "Journal of Food Science: Tamarindus Indica Phytochemistry",
      "Corrosion Engineering: Tartaric Acid Metal Scouring",
      "Indian Chemical Society Transactions"
    ],
    "content": "---\nslug: concept-tartaric-acid-isomer-chelation-chemistry-copper-oxide-dissolution-and-food-preservation\ncategory: concept\nname_en: Tartaric Acid Isomer Chelation Chemistry, Copper Oxide Dissolution & Food Preservation\nname_ta: டார்டாரிக் அமில வேதியியல், தாமிர ஆக்சைடு கரைப்பு மற்றும் உணவுப் பாதுகாப்பு அறிவியல்\nera: Sangam Era to Modern Era\nyear_start: -300\nyear_end: 2026\nthinai: marutham\nsummary_en: The molecular science of Tamarindus indica acidity: high concentrations of natural L(+)-tartaric acid (2,3-dihydroxybutanedioic acid) resisting bacterial degradation, dicarboxylic bidentate chelation bonding with copper and iron cations, lowering of food water activity (aw), and thermal stability up to 175°C preventing loss of sourness during prolonged boiling.\nsummary_ta: புளியின் அமில வேதியியல்: அதிக அளவில் காணப்படும் L(+)-டார்டாரிக் அமிலம், தாமிர மற்றும் இரும்பு அயனிகளுடன் பிணைந்து கறைகளை நீக்கும் 'செலேஷன்' வேதிவினை, பாக்டீரியா வளர்ச்சியைத் தடுக்கும் குறைந்த கார-அமில நிலை (pH 2.8-3.2) மற்றும் 175 பாகை வரை சுவை மாறாமல் கொதிக்கும் வெப்ப நிலைப்புத்தன்மை.\nsources:\n  - Journal of Food Science: Tamarindus Indica Phytochemistry\n  - Corrosion Engineering: Tartaric Acid Metal Scouring\n  - Indian Chemical Society Transactions\n---\n\n# Tartaric Acid Isomer Chelation Chemistry, Copper Oxide Dissolution & Food Preservation\n\nTamarind pulp is biologically unique among edible plant kingdoms: while most fruits derive their acidity from citric or malic acid, tamarind is the only major commercial fruit dominated by **L(+)-tartaric acid** (accounting for 8 to 18 percent of ripe pulp weight).\n\n### 1. Dicarboxylic Bidentate Chelation Structure\n- L(+)-tartaric acid ($\text{C}_4\text{H}_6\text{O}_6$) possesses two carboxylic acid groups ($-\text{COOH}$) and two hydroxyl groups ($-\text{OH}$).\n- This symmetrical stereochemical architecture allows tartaric acid to act as a **bidentate ligand**. The oxygen electron pairs coordinate with transition metal cations ($\text{Cu}^{2+}, \text{Fe}^{3+}$), locking the metal ion into a stable five-membered heterocyclic ring.\n- In metal cleaning (*puli-ittu-vilakki*), this chelation prevents re-precipitation of insoluble copper carbonates, enabling effortless cold-water rinsing without caustic synthetic detergents.\n\n### 2. High Thermal Stability vs Citric Acid\n- While citric acid decomposes rapidly into aconitic acid above 150°C, tartaric acid maintains structural integrity up to 175°C.\n- In slow-simmered temple stews (*Puli Sadham*, *Kuzhambu*), prolonged frying in hot oil does not destroy the sour notes, ensuring that rich acidity survives hours of culinary reduction.\n\n### 3. Antimicrobial Mode of Action\n- Tamarind lowers aqueous food pH to 2.8 - 3.2.\n- Undissociated tartaric acid molecules penetrate lipophilic bacterial cell walls. Once inside the neutral cytoplasm, the acid dissociates into tartrate anions and protons ($\text{H}^+$), acidifying the internal pH and disrupting proton motive force, ATP synthesis, and nutrient transport, resulting in rapid bacterial lysis.\n"
  },
  {
    "slug": "concept-sangam-puli-kari-gastronomy-purananuru-sour-meat-stews-and-digestive-homeostasis",
    "file": "concept-sangam-puli-kari-gastronomy-purananuru-sour-meat-stews-and-digestive-homeostasis.md",
    "category": "concept",
    "name_en": "Sangam Puli-Kari Gastronomy, Purananuru Sour Meat Stews & Digestive Homeostasis",
    "name_ta": "சங்க காலப் புளிக்கறி சமையலியல், புறநானூற்றுப் புளி இறைச்சி மற்றும் செரிமானச் சமநிலை",
    "era": "Sangam Era",
    "year_start": -300,
    "year_end": 300,
    "thinai": "mullai",
    "summary_en": "The gastronomic anthropology of tamarind in Sangam classical poetry: Purananuru and Malaipadukadam descriptions of succulent mutton and wild game stewed with sour tamarind and black pepper (puli-kootu / puli-kari), balancing the heavy Pitta of red meat with tartaric acidity, and fueling warrior endurance.",
    "summary_ta": "சங்க இலக்கியத்தில் புளிக்கறி சமையல் மரபு: புறநானூறு மற்றும் மலைபடுகடாம் காட்டும் கொழுத்த ஆட்டிறைச்சியையும் காட்டிறைச்சியையும் புளி சேர்த்து வேகவைத்து மிளகு தூவிப் படைக்கும் விருந்தோம்பல், இறைச்சியின் மந்தத்தை நீக்கும் செரிமானச் சமநிலை.",
    "sources": [
      "Purananuru 168 (Karuvur Kanthapillai Sathanar)",
      "Malaipadukadam 165-175",
      "Porunararruppadai 105-115"
    ],
    "content": "---\nslug: concept-sangam-puli-kari-gastronomy-purananuru-sour-meat-stews-and-digestive-homeostasis\ncategory: concept\nname_en: Sangam Puli-Kari Gastronomy, Purananuru Sour Meat Stews & Digestive Homeostasis\nname_ta: சங்க காலப் புளிக்கறி சமையலியல், புறநானூற்றுப் புளி இறைச்சி மற்றும் செரிமானச் சமநிலை\nera: Sangam Era\nyear_start: -300\nyear_end: 300\nthinai: mullai\nsummary_en: The gastronomic anthropology of tamarind in Sangam classical poetry: Purananuru and Malaipadukadam descriptions of succulent mutton and wild game stewed with sour tamarind and black pepper (puli-kootu / puli-kari), balancing the heavy Pitta of red meat with tartaric acidity, and fueling warrior endurance.\nsummary_ta: சங்க இலக்கியத்தில் புளிக்கறி சமையல் மரபு: புறநானூறு மற்றும் மலைபடுகடாம் காட்டும் கொழுத்த ஆட்டிறைச்சியையும் காட்டிறைச்சியையும் புளி சேர்த்து வேகவைத்து மிளகு தூவிப் படைக்கும் விருந்தோம்பல், இறைச்சியின் மந்தத்தை நீக்கும் செரிமானச் சமநிலை.\nsources:\n  - Purananuru 168 (Karuvur Kanthapillai Sathanar)\n  - Malaipadukadam 165-175\n  - Porunararruppadai 105-115\n---\n\n# Sangam Puli-Kari Gastronomy, Purananuru Sour Meat Stews & Digestive Homeostasis\n\nIn the classical Sangam corpus, tamarind is celebrated not as an exotic luxury, but as the foundational soul of hospitality (*virundhombal*) and culinary balance across pastoral (*Mullai*) and agricultural (*Marutham*) tracts.\n\n### 1. Purananuru on Tamarind Meat Feasting\n- Classical bards travelling between royal courts frequently describe being served steaming bowls of rice paired with fat venison or mutton stewed in tart tamarind broth:\n  > *\"திதலைப் புளிங்கறி சோறு...\"*  \n  *(Steaming white rice soaked in pungent meat broth simmered with rich sour tamarind).*\n- In *Purananuru* 168, the patron chieftain Pittan Korran feeds passing warriors and singers with fatty roasted meat steeped in tamarind soup to restore vigor after exhausting cross-country marches.\n\n### 2. Malaipadukadam Forest Cuisine\n- In *Malaipadukadam*, the mountain tribes cook wild boar chops and monitor lizard meat seasoned with tamarind extract, wild black pepper, and roasted bamboo seeds in earthen pots over log fires.\n- The sourness softened tough game muscle and stimulated digestive secretions (*jatharagni*), preventing heaviness and toxic indigestion (*aama dosha*).\n\n### 3. Evolutionary Legacy in Modern Tamil Cooking\n- This ancient pairing evolved directly into modern staples:\n  - **Puli Kuzhambu**: Tamarind stew with dried berries (*vathal*).\n  - **Meen Kuzhambu**: Tamarind fish curry where acidity neutralizes fishy amines.\n  - **Kovil Puli Sadham**: Temple tamarind rice tempered with peanuts, fenugreek, and sesame oil, durable for travel without spoilage.\n"
  },
  {
    "slug": "concept-ancient-tamil-puliya-thoppu-roadside-avenue-forestry-soil-binding-and-communal-usufruct",
    "file": "concept-ancient-tamil-puliya-thoppu-roadside-avenue-forestry-soil-binding-and-communal-usufruct.md",
    "category": "concept",
    "name_en": "Ancient Tamil Puliya-Thoppu Roadside Avenue Forestry, Soil Binding & Communal Usufruct",
    "name_ta": "பண்டைத் தமிழகப் புளியந்தோப்புச் சாலை நிழற்காடுகள், மண் பாதுகாப்பு மற்றும் சமுதாய அனுபவ உரிமை",
    "era": "Medieval Chola to Modern Era",
    "year_start": 900,
    "year_end": 2026,
    "thinai": "mullai",
    "summary_en": "Ecological and civic arboriculture: the systematic planting of tamarind groves (Puliya-Thoppu) along highway trade arteries (peruvazhi) by medieval Tamil kings and village assemblies (Ur / Sabha), acting as living rest canopies for travellers, deep taproot erosion-control barriers in semi-arid soils, and generating communal auction revenue.",
    "summary_ta": "சோழர் மற்றும் நாயக்கர் காலச் சாலை ஓரப் புளியந்தோப்புகள்: பெருவழிகளில் பயணிகளுக்கு நிழல் தரும் காடுகள், வறண்ட நிலத்தில் வேர் ஊன்றி மண் அரிப்பைத் தடுக்கும் சூழலியல் காப்பு மற்றும் ஊர் அவைகளால் ஏலமிடப்பட்டு பொது நல நிதி திரட்டும் சமுதாய அனுபவ முறைமை.",
    "sources": [
      "Uttiramerur Temple Inscriptions on Village Groves",
      "South Indian Inscriptions Vol. XIV: Chola Highways",
      "Arboricultural History of Peninsular India"
    ],
    "content": "---\nslug: concept-ancient-tamil-puliya-thoppu-roadside-avenue-forestry-soil-binding-and-communal-usufruct\ncategory: concept\nname_en: Ancient Tamil Puliya-Thoppu Roadside Avenue Forestry, Soil Binding & Communal Usufruct\nname_ta: பண்டைத் தமிழகப் புளியந்தோப்புச் சாலை நிழற்காடுகள், மண் பாதுகாப்பு மற்றும் சமுதாய அனுபவ உரிமை\nera: Medieval Chola to Modern Era\nyear_start: 900\nyear_end: 2026\nthinai: mullai\nsummary_en: Ecological and civic arboriculture: the systematic planting of tamarind groves (Puliya-Thoppu) along highway trade arteries (peruvazhi) by medieval Tamil kings and village assemblies (Ur / Sabha), acting as living rest canopies for travellers, deep taproot erosion-control barriers in semi-arid soils, and generating communal auction revenue.\nsummary_ta: சோழர் மற்றும் நாயக்கர் காலச் சாலை ஓரப் புளியந்தோப்புகள்: பெருவழிகளில் பயணிகளுக்கு நிழல் தரும் காடுகள், வறண்ட நிலத்தில் வேர் ஊன்றி மண் அரிப்பைத் தடுக்கும் சூழலியல் காப்பு மற்றும் ஊர் அவைகளால் ஏலமிடப்பட்டு பொது நல நிதி திரட்டும் சமுதாய அனுபவ முறைமை.\nsources:\n  - Uttiramerur Temple Inscriptions on Village Groves\n  - South Indian Inscriptions Vol. XIV: Chola Highways\n  - Arboricultural History of Peninsular India\n---\n\n# Ancient Tamil Puliya-Thoppu Roadside Avenue Forestry, Soil Binding & Communal Usufruct\n\nThe tamarind tree is a biological monument of peninsular civil engineering, drought defiance, and civic welfare across Tamil country.\n\n### 1. Imperial Highway Avenues (*பெருவழிப் புளியந்தோப்புகள்*)\n- Under the Cholas and Vijayanagara Nayakas, state-engineered royal highways (*Raja-gambhira-peruvazhi*, *Kongu-peruvazhi*) were flanked on both flanks by double rows of tamarind trees spaced 30 feet apart.\n- Tamarind trees tolerate scorching summer heat, poor gravelly clay, and annual rainfall as low as 400 mm, producing dense dome-shaped umbrella canopies that lowered ambient road surface temperatures by 6 to 10°C for pack-bullocks, soldiers, and pedestrians.\n\n### 2. Deep Taproot & Soil Conservation\n- The massive taproot system penetrates 4 to 6 metres into fractured gneiss bedrock, while spreading lateral roots anchor loose topsoil against torrential monsoon gullying.\n- Planting *Puliya-Thoppu* along tank bunds (*eri-karai*) prevented earthen embankment breaches during sudden flash floods.\n\n### 3. Communal Usufruct & Public Finance (*ஊர் அனுபவ உரிமை*)\n- Unlike sacred temple gardens (*nandavanam*) with restricted access, village avenue groves were held as communal commons (*podhu-udamai*).\n- Epigraphs from Uttiramerur record that annual rights to harvest roadside tamarind pods were auctioned by the village assembly (*Ur-Sabha*). Proceeds were deposited in the irrigation maintenance fund (*eri-variyam*) to desilt local feeder canals.\n"
  },
  {
    "slug": "institution-village-ur-assembly-puli-grove-commons-trusts-and-temple-puli-sadham-endowments",
    "file": "institution-village-ur-assembly-puli-grove-commons-trusts-and-temple-puli-sadham-endowments.md",
    "category": "institution",
    "name_en": "Village Ur-Assembly Puli Grove Commons Trusts & Temple Puli-Sadham Endowments",
    "name_ta": "கிராம ஊரவை புளியந்தோப்பு அறக்கட்டளைகள் மற்றும் கோயில் புளியோதரைப் பிரசாத அறக்கொடைகள்",
    "era": "Medieval Chola to Nayaka Era",
    "year_start": 950,
    "year_end": 1700,
    "thinai": "marutham",
    "summary_en": "The institutional governance of tamarind production and utilization: village self-governing assemblies (Ur and Sabha) administering common orchard leases, settling boundary disputes over fruiting trees, and medieval donor endowments funding perpetual daily tamarind rice (Puli-Ogarai / Puli-Sadham) offerings at major Vaishnavite and Saivite temples.",
    "summary_ta": "புளி சாகுபடி மற்றும் பயன்பாட்டின் நிறுவனக் கட்டமைப்பு: ஊரவைகளின் புளியந்தோப்பு குத்தகை நிர்வாகம், எல்லை மரங்களின் உரிமைத் தீர்ப்புகள் மற்றும் திருச்சி ஸ்ரீரங்கம், மதுரை, காஞ்சி கோயில்களில் புளியோதரைப் பிரசாதம் நித்தியப் படியாக வழங்கப்பட்ட அறக்கொடை ஆவணங்கள்.",
    "sources": [
      "Srirangam Temple Inscriptions (Epigraphia Indica Vol. XXIV)",
      "Chidambaram Nataraja Temple Epigraphical Records",
      "Tirumala-Tirupati Devasthanam Inscriptions (Puli-Ogarai Grants)"
    ],
    "content": "---\nslug: institution-village-ur-assembly-puli-grove-commons-trusts-and-temple-puli-sadham-endowments\ncategory: institution\nname_en: Village Ur-Assembly Puli Grove Commons Trusts & Temple Puli-Sadham Endowments\nname_ta: கிராம ஊரவை புளியந்தோப்பு அறக்கட்டளைகள் மற்றும் கோயில் புளியோதரைப் பிரசாத அறக்கொடைகள்\nera: Medieval Chola to Nayaka Era\nyear_start: 950\nyear_end: 1700\nthinai: marutham\nsummary_en: The institutional governance of tamarind production and utilization: village self-governing assemblies (Ur and Sabha) administering common orchard leases, settling boundary disputes over fruiting trees, and medieval donor endowments funding perpetual daily tamarind rice (Puli-Ogarai / Puli-Sadham) offerings at major Vaishnavite and Saivite temples.\nsummary_ta: புளி சாகுபடி மற்றும் பயன்பாட்டின் நிறுவனக் கட்டமைப்பு: ஊரவைகளின் புளியந்தோப்பு குத்தகை நிர்வாகம், எல்லை மரங்களின் உரிமைத் தீர்ப்புகள் மற்றும் திருச்சி ஸ்ரீரங்கம், மதுரை, காஞ்சி கோயில்களில் புளியோதரைப் பிரசாதம் நித்தியப் படியாக வழங்கப்பட்ட அறக்கொடை ஆவணங்கள்.\nsources:\n  - Srirangam Temple Inscriptions (Epigraphia Indica Vol. XXIV)\n  - Chidambaram Nataraja Temple Epigraphical Records\n  - Tirumala-Tirupati Devasthanam Inscriptions (Puli-Ogarai Grants)\n---\n\n# Village Ur-Assembly Puli Grove Commons Trusts & Temple Puli-Sadham Endowments\n\nThe economic management of tamarind reveals an institutional convergence of village revenue boards and monumental temple endowments.\n\n### 1. Village Assembly Grove Administration (*ஊர் சபை புளி நிர்வாகம்*)\n- Under Chola local administration, village charters (*vyavasthai*) defined strict penal codes against cutting live fruiting tamarind trees (*pazha-maram-vettal*). Offenders were fined gold *kasus* paid into the village treasury.\n- Village assemblies established lease contracts where contractors paid fixed measures of deseeded, salted tamarind (*mattai-puli*) into civic granaries for lean season redistribution.\n\n### 2. Temple Perpetual Feasting Endowments (*புளியோதரை அறக்கொடைகள்*)\n- Epigraphs at Srirangam Ranganathaswamy Temple, Kanchipuram Varadaraja Perumal Temple, and Tirumala comprehensively list gold, paddy land, and cash endowments (*kattalai*) established by kings, military generals (*senapathis*), and merchant guilds to provide perpetual daily pots of **Puli-Ogarai** (tamarind rice).\n- The standardized ritual recipe recorded in temple inscriptions specified exact ratios: polished samba paddy, thick dark aged tamarind extract (*pazham-puli*), sesame oil (*nallennai*), mustard seeds, dried red chillies, split urad dal, chana dal, roasted groundnuts, curry leaves, and asafoetida (*perungayam*).\n\n### 3. Food Security for Pilgrims & Festivals\n- Because tamarind rice resists bacterial decay for 3 to 4 days even in intense heat, temple trusts distributed thousands of clay bowls (*satti*) of Puli-Ogarai to pilgrims during Brahmotsavam festivals, creating an ancient system of shelf-stable public food relief.\n"
  },
  {
    "slug": "place-tindivanam-ancient-thondaimandalam-puli-tamarind-agroforestry-haven",
    "file": "place-tindivanam-ancient-thondaimandalam-puli-tamarind-agroforestry-haven.md",
    "category": "place",
    "name_en": "Tindivanam: Ancient Thondaimandalam Puli Tamarind Agroforestry Haven",
    "name_ta": "திண்டிவனம்: தொண்டை மண்டலப் புளியந்தோப்பு மற்றும் புளி வர்த்தகத் தலைநகரம்",
    "era": "Medieval to Modern Era",
    "year_start": 800,
    "year_end": 2026,
    "thinai": "mullai",
    "summary_en": "Geographical and historical profile of Tindivanam (ancient Thinthirini-vanam, meaning 'Tamarind Forest' in Sanskrit and Tamil): the historic epicenter of dryland tamarind agroforestry, avenue groves, and bulk spice mandis in Thondaimandalam (Villupuram district, Tamil Nadu).",
    "summary_ta": "தொண்டை மண்டலத்தின் திண்டிவனம் (திந்திரிணி-வனம் / புளியங்காடு) நகரின் புவியியல் மற்றும் வரலாற்றுப் பின்னணி: பரந்து விரிந்த புளியந்தோப்புகள், பண்டைய பெருவழி நிழற்காடுகள் மற்றும் தென்னிந்தியப் புளி வணிகத்தின் முதன்மை மண்டிகளின் வரலாற்று மையம்.",
    "sources": [
      "Villupuram District Epigraphical Survey",
      "South Indian Inscriptions: Thondaimandalam Grants",
      "Agricultural Marketing Board Records on Tindivanam Tamarind Mandi"
    ],
    "content": "---\nslug: place-tindivanam-ancient-thondaimandalam-puli-tamarind-agroforestry-haven\ncategory: place\nname_en: Tindivanam: Ancient Thondaimandalam Puli Tamarind Agroforestry Haven\nname_ta: திண்டிவனம்: தொண்டை மண்டலப் புளியந்தோப்பு மற்றும் புளி வர்த்தகத் தலைநகரம்\nera: Medieval to Modern Era\nyear_start: 800\nyear_end: 2026\nthinai: mullai\nsummary_en: Geographical and historical profile of Tindivanam (ancient Thinthirini-vanam, meaning 'Tamarind Forest' in Sanskrit and Tamil): the historic epicenter of dryland tamarind agroforestry, avenue groves, and bulk spice mandis in Thondaimandalam (Villupuram district, Tamil Nadu).\nsummary_ta: தொண்டை மண்டலத்தின் திண்டிவனம் (திந்திரிணி-வனம் / புளியங்காடு) நகரின் புவியியல் மற்றும் வரலாற்றுப் பின்னணி: பரந்து விரிந்த புளியந்தோப்புகள், பண்டைய பெருவழி நிழற்காடுகள் மற்றும் தென்னிந்தியப் புளி வணிகத்தின் முதன்மை மண்டிகளின் வரலாற்று மையம்.\nsources:\n  - Villupuram District Epigraphical Survey\n  - South Indian Inscriptions: Thondaimandalam Grants\n  - Agricultural Marketing Board Records on Tindivanam Tamarind Mandi\n---\n\n# Tindivanam: Ancient Thondaimandalam Puli Tamarind Agroforestry Haven\n\n**Coordinates:** `12.2272° N, 79.6515° E`  \n**Etymology:** Derived from *Thinthirini-vanam* (Sanskrit *Tintidika* / Tamil *Thinthirini* = Tamarind tree; *Vanam* = Forest)  \n**Landscape Ecosystem:** Red lateritic scrub and dry deciduous woodland (*Mullai thinai*)  \n**Modern District:** Villupuram District, Tamil Nadu  \n\n### 1. Etymological & Sacred Origins\n- The name **Tindivanam** directly translates to **\"The Forest of Tamarind Trees\"**.\n- Medieval inscriptions and temple sthala-puranas commemorate how ancient hermitages and shrines were established within endless natural groves of wild and planted tamarind along the dry plains of northern Tamil Nadu.\n\n### 2. Strategic Agro-Climatic Crossroads\n- Situated at the junction of the grand northern highways linking Kanchipuram and Chennai with Tiruchirappalli and Thanjavur, Tindivanam evolved as the primary collecting depot for tamarind harvests from Gingee, Pennagaram, and Tiruvannamalai hills.\n- Red ferruginous soils and semi-arid conditions stimulate deep sugar concentration and low water content in the local tamarind pods, yielding sticky, dark, high-acid pulp prized for storage.\n\n### 3. Modern Commercial Continuity\n- Tindivanam continues to host one of peninsular India's largest regulated tamarind mandis, processing thousands of tons of deseeded flower tamarind (*poop-puli*) and compressed slab tamarind traded across all southern states.\n"
  },
  {
    "slug": "text-purananuru-and-chola-epigraphs-on-puliya-maram-groves-tamarind-taxation-and-feasting",
    "file": "text-purananuru-and-chola-epigraphs-on-puliya-maram-groves-tamarind-taxation-and-feasting.md",
    "category": "text",
    "name_en": "Purananuru & Chola Epigraphs on Puliya-Maram Groves, Tamarind Taxation and Feasting",
    "name_ta": "புறநானூறு மற்றும் சோழர் கல்வெட்டுகளில் புளியமரத் தோப்புகள், புளி வரி மற்றும் விருந்துப் பதிவுகள்",
    "era": "Sangam to Medieval Chola Era",
    "year_start": -200,
    "year_end": 1250,
    "thinai": "marutham",
    "summary_en": "Classical verses and medieval epigraphical documents recording tamarind economy: Purananuru celebration of tamarind-stewed feasts, Chola stone inscriptions documenting taxation on fruit-bearing tamarind groves (puli-irai / tharu-irai), and imperial decrees protecting sacred temple tamarind trees.",
    "summary_ta": "செவ்வியல் இலக்கியம் மற்றும் சோழர் கல்வெட்டுகளில் புளிப் பதிவுகள்: புறநானூற்றில் புளிக்கறி விருந்துப் பாடல்கள், பலன் தரும் புளியமரங்களுக்கான சோழர் காலப் புளி வரி மற்றும் கோயில் புளியமரங்களைப் பாதுகாக்கும் அரச ஆணைகள்.",
    "sources": [
      "Purananuru 168 & 390",
      "South Indian Inscriptions Vol. II: Thanjavur Inscriptions",
      "Epigraphia Indica: Chola Land Revenue Assessments"
    ],
    "content": "---\nslug: text-purananuru-and-chola-epigraphs-on-puliya-maram-groves-tamarind-taxation-and-feasting\ncategory: text\nname_en: Purananuru & Chola Epigraphs on Puliya-Maram Groves, Tamarind Taxation and Feasting\nname_ta: புறநானூறு மற்றும் சோழர் கல்வெட்டுகளில் புளியமரத் தோப்புகள், புளி வரி மற்றும் விருந்துப் பதிவுகள்\nera: Sangam to Medieval Chola Era\nyear_start: -200\nyear_end: 1250\nthinai: marutham\nsummary_en: Classical verses and medieval epigraphical documents recording tamarind economy: Purananuru celebration of tamarind-stewed feasts, Chola stone inscriptions documenting taxation on fruit-bearing tamarind groves (puli-irai / tharu-irai), and imperial decrees protecting sacred temple tamarind trees.\nsummary_ta: செவ்வியல் இலக்கியம் மற்றும் சோழர் கல்வெட்டுகளில் புளிப் பதிவுகள்: புறநானூற்றில் புளிக்கறி விருந்துப் பாடல்கள், பலன் தரும் புளியமரங்களுக்கான சோழர் காலப் புளி வரி மற்றும் கோயில் புளியமரங்களைப் பாதுகாக்கும் அரச ஆணைகள்.\nsources:\n  - Purananuru 168 & 390\n  - South Indian Inscriptions Vol. II: Thanjavur Inscriptions\n  - Epigraphia Indica: Chola Land Revenue Assessments\n---\n\n# Purananuru & Chola Epigraphs on Puliya-Maram Groves, Tamarind Taxation and Feasting\n\nThe economic and gastronomic footprint of tamarind is permanently carved into Sangam poetry and thousands of stone inscriptions across Tamil Nadu.\n\n### 1. Purananuru: The Feast of the Warrior Chief\n- In *Purananuru* 390, poet Karuvur Kanthapillai Sathanar extols the generous feasting given by chieftain Pittan Korran:\n  > *\"புளிப்பெய்து அட்ட சுவைக்கனி மிளகின்...\"*  \n  *(Savory fruit broth boiled with rich sour tamarind and freshly crushed black pepper, served alongside venison and rice to banish poverty).*\n- The verses confirm that tamarind stewing with black pepper was the canonical seasoning method for game in ancient Tamilakam.\n\n### 2. Chola Revenue Inscriptions: Puli-Irai (*புளி வரி*)\n- Under the revenue surveys of Rajaraja Chola I and Kulothunga Chola I (*kettuk-kann-azhithal*), land classification distinguished between uncultivated scrub and productive arboricultural groves.\n- Inscriptions at Tiruvidaimarudur and Thanjavur designate a specific tax on productive fruiting tamarind trees: **புளிக் கடமை (Puli-Kadamai)** or **மர இறை (Mara-Irai)**.\n- If a farmer converted dry wasteland into a tamarind grove (*thoppu*), tax was remitted for the first seven years until the trees reached fruiting maturity, after which fixed annual measures of salted tamarind were remitted to the state.\n\n### 3. Protective Decrees for Sacred Groves\n- Inscriptions at temple gates often concluded with royal decrees stating that anyone cutting down temple avenue tamarind trees would incur the sin of slaughtering holy cows on the banks of the Ganges, testifying to the sanctified protection accorded to these long-lived shade-bearers.\n"
  }
]

EDGES = [
  [
    "technology-puli-pod-harvesting-deseeding-rock-salt-compacting-and-mattai-puli-maturation-technology",
    "located_in",
    "place-tindivanam-ancient-thondaimandalam-puli-tamarind-agroforestry-haven",
    "material_culture",
    "Sangam Era to Modern Era",
    "Tindivanam is the historic Thondaimandalam haven for tamarind harvesting and mattai-puli curing",
    "Villupuram Epigraphs"
  ],
  [
    "technology-puli-pod-harvesting-deseeding-rock-salt-compacting-and-mattai-puli-maturation-technology",
    "utilizes_artifact",
    "artifact-salted-mattai-puli-earthenware-bharani-wooden-pod-mallets-and-bronze-kinnam-pots",
    "material_culture",
    "Sangam Era to Modern Era",
    "Salted mattai puli blocks and earthenware bharani jars are produced during post-harvest curing",
    "Traditional Knowledge Registers"
  ],
  [
    "technology-puli-ittu-vilakki-tartaric-acid-chelation-brass-bronze-cleaning-and-culinary-acid-stewing-technology",
    "applies_concept",
    "concept-tartaric-acid-isomer-chelation-chemistry-copper-oxide-dissolution-and-food-preservation",
    "material_culture",
    "Sangam Era to Modern Era",
    "Puli-ittu-vilakki directly applies tartaric acid chelation to dissolve copper oxide and verdigris",
    "Corrosion Science"
  ],
  [
    "technology-puli-ittu-vilakki-tartaric-acid-chelation-brass-bronze-cleaning-and-culinary-acid-stewing-technology",
    "utilizes_artifact",
    "artifact-tamarind-wood-mortar-pestles-charcoal-braziers-and-puli-kuzhambu-clay-chatti-cookware",
    "material_culture",
    "Medieval Era to Modern Era",
    "Clay manchatti cookware and tamarind wood charcoal braziers are used for stewing puli kuzhambu",
    "Purananuru 29"
  ],
  [
    "concept-sangam-puli-kari-gastronomy-purananuru-sour-meat-stews-and-digestive-homeostasis",
    "documented_in",
    "text-purananuru-and-chola-epigraphs-on-puliya-maram-groves-tamarind-taxation-and-feasting",
    "material_culture",
    "Sangam Era",
    "Purananuru 168 and 390 document the ancient tradition of sour tamarind meat stews (puli-kari)",
    "Purananuru 168"
  ],
  [
    "concept-ancient-tamil-puliya-thoppu-roadside-avenue-forestry-soil-binding-and-communal-usufruct",
    "manifested_at",
    "place-tindivanam-ancient-thondaimandalam-puli-tamarind-agroforestry-haven",
    "material_culture",
    "Medieval Era",
    "Tindivanam (ancient Thinthirini-vanam) arose as a grand network of tamarind avenue groves",
    "Thondaimandalam Grants"
  ],
  [
    "institution-village-ur-assembly-puli-grove-commons-trusts-and-temple-puli-sadham-endowments",
    "organizes_practice",
    "concept-ancient-tamil-puliya-thoppu-roadside-avenue-forestry-soil-binding-and-communal-usufruct",
    "material_culture",
    "Medieval Chola Era",
    "Village Ur assemblies leased roadside tamarind groves to fund civic irrigation works",
    "Uttiramerur Inscriptions"
  ],
  [
    "institution-village-ur-assembly-puli-grove-commons-trusts-and-temple-puli-sadham-endowments",
    "documented_in",
    "text-purananuru-and-chola-epigraphs-on-puliya-maram-groves-tamarind-taxation-and-feasting",
    "material_culture",
    "Medieval Chola Era",
    "Chola epigraphs record tamarind tax assessments and temple Puli-Sadham endowments",
    "South Indian Inscriptions"
  ],
  [
    "artifact-salted-mattai-puli-earthenware-bharani-wooden-pod-mallets-and-bronze-kinnam-pots",
    "embodies_concept",
    "concept-tartaric-acid-isomer-chelation-chemistry-copper-oxide-dissolution-and-food-preservation",
    "material_culture",
    "Medieval Era",
    "Glazed ceramic bharani jars safely store tartaric-acid-rich salted tamarind without corrosion",
    "Thanjavur Inscriptions"
  ],
  [
    "concept-sangam-puli-kari-gastronomy-purananuru-sour-meat-stews-and-digestive-homeostasis",
    "applies_concept",
    "concept-tartaric-acid-isomer-chelation-chemistry-copper-oxide-dissolution-and-food-preservation",
    "material_culture",
    "Sangam Era",
    "Tartaric acidity in meat stewing tenderizes muscle collagen and inhibits bacterial spoil",
    "Food Science Studies"
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
