#!/usr/bin/env python3
"""
Harvester: Batch 56 - Ancient Tamil Cardamom (Elakkai) & Western Ghats Hill Spicery
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
    "slug": "technology-elakkai-understory-agroforestry-hand-harvesting-and-curing-kiln-technology",
    "file": "technology-elakkai-understory-agroforestry-hand-harvesting-and-curing-kiln-technology.md",
    "category": "technology",
    "name_en": "Elakkai Understory Agroforestry, Hand Harvesting & Curing Kiln Technology",
    "name_ta": "ஏலக்காய் நிழல்மரக் காட்டியல், கை அறுவடை மற்றும் உலர்த்துக் களத் தொழில்நுட்பம்",
    "era": "Sangam Era to Modern Era",
    "year_start": -300,
    "year_end": 2026,
    "thinai": "kurinji",
    "summary_en": "High-altitude evergreen forest understory cultivation of Elettaria cardamomum in the Western Ghats (Cardamom Hills / Anamalai / Bodinayakkanur): selective hand-stripping of capsules at three-quarter maturity, washing in copper pans, and wood-smoke or indirect flue-pipe curing inside traditional thatched drying sheds (bhatti / elakkai pukaikoottu) to retain vivid emerald chlorophyll and prevent dehiscence.",
    "summary_ta": "மேற்குத் தொடர்ச்சி மலை ஏலக்காய் மலைத்தொடர் மற்றும் போடிநாயக்கனூர் நிழல்மரக் காடுகளில் ஏலக்காய் சாகுபடி, முக்கால் பக்குவத்தில் விரலால் கிள்ளி அறுவடை செய்தல் மற்றும் மர எரிகுழல் உலர்த்துக் கூடங்களில் பசுமை மாறாமல் பதப்படுத்தும் தொழில்நுட்பம்.",
    "sources": [
      "Pathitruppathu 11",
      "Silappadikaram: Ur-Kaan Kathai",
      "Spices Board Post-Harvest Technology Manuals"
    ],
    "content": "---\nslug: technology-elakkai-understory-agroforestry-hand-harvesting-and-curing-kiln-technology\ncategory: technology\nname_en: Elakkai Understory Agroforestry, Hand Harvesting & Curing Kiln Technology\nname_ta: ஏலக்காய் நிழல்மரக் காட்டியல், கை அறுவடை மற்றும் உலர்த்துக் களத் தொழில்நுட்பம்\nera: Sangam Era to Modern Era\nyear_start: -300\nyear_end: 2026\nthinai: kurinji\nsummary_en: High-altitude evergreen forest understory cultivation of Elettaria cardamomum in the Western Ghats (Cardamom Hills / Anamalai / Bodinayakkanur): selective hand-stripping of capsules at three-quarter maturity, washing in copper pans, and wood-smoke or indirect flue-pipe curing inside traditional thatched drying sheds (bhatti / elakkai pukaikoottu) to retain vivid emerald chlorophyll and prevent dehiscence.\nsummary_ta: மேற்குத் தொடர்ச்சி மலை ஏலக்காய் மலைத்தொடர் மற்றும் போடிநாயக்கனூர் நிழல்மரக் காடுகளில் ஏலக்காய் சாகுபடி, முக்கால் பக்குவத்தில் விரலால் கிள்ளி அறுவடை செய்தல் மற்றும் மர எரிகுழல் உலர்த்துக் கூடங்களில் பசுமை மாறாமல் பதப்படுத்தும் தொழில்நுட்பம்.\nsources:\n  - Pathitruppathu 11\n  - Silappadikaram: Ur-Kaan Kathai\n  - Spices Board Post-Harvest Technology Manuals\n---\n\n# Elakkai Understory Agroforestry, Hand Harvesting & Curing Kiln Technology\n\nThe cultivation and preservation of cardamom (**Elettaria cardamomum**, Tamil: **ஏலக்காய் / Elakkai**, also anciently termed *Elam* / ஏலம்) represents the pinnacle of high-elevation montane agroforestry in the ancient Tamil country (*Kurinji thinai*).\n\n### 1. Forest Understory Ecology & Canopy Management\n- Native cardamom flourishes exclusively in humid, organic-rich humus understories of Western Ghats evergreen rain forests between 800 and 1,500 metres elevation.\n- Ancient cultivators maintained multi-tier shade tree canopies (such as *Artocarpus heterophyllus*, *Terminalia*, and *Ficus* species) providing 50 to 60 percent filtered canopy shade. Cardamom plants possess shallow adventitious fibrous root mats that feed upon perpetual leaf-litter mulch (*sarugu* / சருகு).\n\n### 2. Selective Hand Harvesting\n- Flower panicles radiate from the base of pseudostems along the ground. Because panicles flower sequentially over 5 to 6 months (from August to February), uniform mechanical harvesting is impossible.\n- Skilled hill harvesters selectively hand-strip individual capsules at three-quarter physiological maturity—when the dark brown seeds inside turn firm and black, but before the green pericarp splits (*dehiscence*).\n- Immature capsules shrink into wrinkled grey hulls; overripe capsules split open upon drying, losing volatile oils.\n\n### 3. Washing & Soaking\n- Freshly plucked capsules are washed in spring water inside perforated wooden or copper vats to remove adhering humus and red forest earth.\n- In ancient processing, capsules were quickly steeped in dilute plant-ash alkaline wash or mild washing soda solution (0.1 percent) to clean surface oils and fix the chlorophyll complex, preserving the prized deep green colour.\n\n### 4. Kiln Curing Architecture (*ஏலக்காய் புகைக்கூடு / Elakkai Pukaikoottu*)\n- Curing must reduce moisture from 80-84 percent down to 10-12 percent within 24 to 30 hours, without exceeding 50 degrees Celsius to prevent vaporization of delicate volatile terpenes.\n- Ancient hill sheds used raised split-bamboo drying lofts (*paranai*) suspended over smouldering hearths fueled by non-resinous jungle hardwoods, maintaining warm circulating air draft.\n- In later traditional kilns (*bhatti* system), an external brick furnace heated iron or earthenware pipes passing beneath the drying shelves, establishing an indirect hot-air drying system that cured the cardamom without direct smoke deposition, preserving pristine emerald sheen and pungent floral bouquet.\n"
  },
  {
    "slug": "technology-elakkai-cardamom-essential-oil-hydrodistillation-and-siddha-carminative-compounding-technology",
    "file": "technology-elakkai-cardamom-essential-oil-hydrodistillation-and-siddha-carminative-compounding-technology.md",
    "category": "technology",
    "name_en": "Elakkai Cardamom Essential Oil Hydrodistillation & Siddha Carminative Compounding Technology",
    "name_ta": "ஏலக்காய் நறுமணத் தைலக் காய்ச்சிவடித்தல் மற்றும் சித்த செரிமான மருந்து கூட்டுத் தொழில்நுட்பம்",
    "era": "Sangam Era to Modern Era",
    "year_start": -300,
    "year_end": 2026,
    "thinai": "kurinji",
    "summary_en": "Traditional Siddha hydrodistillation and pharmacognostic pulverization of cardamom seeds: crushing decorticated black seeds immediately prior to water-steam extraction, and compounding Elathi Chooranam with cinnamon, nagakesaram, and dry ginger in palm jaggery or honey for gastrointestinal carminative therapy.",
    "summary_ta": "ஏலக்காய் விதைகளைத் தோலுரித்து நசுக்கி நீராவியில் காய்ச்சி வடித்து நறுமணத் தைலம் பிரித்தெடுத்தல் மற்றும் ஏலாதிச் சூரணம், இலவங்கம், சிறுநாகப்பூ ஆகியவற்றுடன் பனைவெல்லம் கூட்டிச் செய்யப்படும் சித்த செரிமான மருந்து தயாரிக்கும் தொழில்நுட்பம்.",
    "sources": [
      "Agathiyar Gunavagadam",
      "Therayar Yamaga Venba",
      "Siddha Formulary of India"
    ],
    "content": "---\nslug: technology-elakkai-cardamom-essential-oil-hydrodistillation-and-siddha-carminative-compounding-technology\ncategory: technology\nname_en: Elakkai Cardamom Essential Oil Hydrodistillation & Siddha Carminative Compounding Technology\nname_ta: ஏலக்காய் நறுமணத் தைலக் காய்ச்சிவடித்தல் மற்றும் சித்த செரிமான மருந்து கூட்டுத் தொழில்நுட்பம்\nera: Sangam Era to Modern Era\nyear_start: -300\nyear_end: 2026\nthinai: kurinji\nsummary_en: Traditional Siddha hydrodistillation and pharmacognostic pulverization of cardamom seeds: crushing decorticated black seeds immediately prior to water-steam extraction, and compounding Elathi Chooranam with cinnamon, nagakesaram, and dry ginger in palm jaggery or honey for gastrointestinal carminative therapy.\nsummary_ta: ஏலக்காய் விதைகளைத் தோலுரித்து நசுக்கி நீராவியில் காய்ச்சி வடித்து நறுமணத் தைலம் பிரித்தெடுத்தல் மற்றும் ஏலாதிச் சூரணம், இலவங்கம், சிறுநாகப்பூ ஆகியவற்றுடன் பனைவெல்லம் கூட்டிச் செய்யப்படும் சித்த செரிமான மருந்து தயாரிக்கும் தொழில்நுட்பம்.\nsources:\n  - Agathiyar Gunavagadam\n  - Therayar Yamaga Venba\n  - Siddha Formulary of India\n---\n\n# Elakkai Cardamom Essential Oil Hydrodistillation & Siddha Carminative Compounding Technology\n\nCardamom seed processing in classical Siddha pharmacy (*Elam Mathirai* and *Elathi Chooranam*) requires exacting thermodynamic control because the active mono- and sesqui-terpenes evaporate rapidly once the protective fibrous pod is punctured.\n\n### 1. Decortication & Immediate Pulverization\n- Cardamom seeds (*Elam arisi* / ஏல அரிசி) are retained inside the fibrous pericarp until the exact hour of compounding.\n- Dehusking is performed by gentle rolling under wooden mallets (*marakattai*) on granite slabs, separating the light pericarp husks by winnowing (*sulaku* / சுளகு).\n- The aromatic resinous black seeds are immediately powdered in chilled brass mortar (*vengala ural*) to avoid friction heat, which causes premature volatilization of 1,8-cineole and alpha-terpinyl acetate.\n\n### 2. Traditional Clay Deg Hydrodistillation\n- For aromatic extracts (*Elam thailam* / ஏலத் தைலம்), coarsely crushed seeds are steeped in pure mountain spring water inside a wide-bellied copper or earthenware alembic (*kuthirai / vadigalam*).\n- A sealed terracotta helm or bent bamboo duct condenses the aromatic distillate into a recipient flask submerged in cold running stream water.\n- The volatile oil floats atop the hydrolat (aromatic cardamom water / *elakkai theertham*) and is separated using narrow-necked clay skimming funnels.\n\n### 3. Pharmacological Blending: Elathi Chooranam\n- The classical formulation *Elathi Chooranam* combines:\n  - Cardamom (*Elam*, 1 part)\n  - Cinnamon bark (*Lavangapattai*, 2 parts)\n  - Nagakesaram blossom buds (*Sirunagappoo*, 4 parts)\n  - Black pepper (*Milagu*, 8 parts)\n  - Sukku / dry ginger (16 parts)\n  - Piper longum (*Thippili*, 32 parts)\n- Blended with crystalline palm candy or mountain honey, this compounding produces a potent carminative that stimulates gastric peristalsis, clears upper respiratory phlegm, and neutralizes halitosis.\n"
  },
  {
    "slug": "artifact-green-cardamom-seed-capsules-woven-bamboo-drying-racks-and-earthen-storage-bharani",
    "file": "artifact-green-cardamom-seed-capsules-woven-bamboo-drying-racks-and-earthen-storage-bharani.md",
    "category": "artifact",
    "name_en": "Green Cardamom Seed Capsules, Woven Bamboo Drying Racks & Earthen Storage Bharani",
    "name_ta": "பசுமை ஏலக்காய் நெற்றுகள், பின்னல் மூங்கில் பரண்கள் மற்றும் மண்பாண்ட ஏலக்காய் பரணி",
    "era": "Sangam Era to Modern Era",
    "year_start": -300,
    "year_end": 2026,
    "thinai": "kurinji",
    "summary_en": "The physical apparatus of Tamil cardamom handling: three-sided oval green capsules with resinous black aromatic seeds, multi-tiered woven bamboo drying slats (paranai) hung above curing embers, and glazed earthenware storage jars (bharani) sealed with beeswaxed linen to preserve volatile oils.",
    "summary_ta": "தமிழ் மலைப்பகுதி ஏலக்காய் பதனிடப் பயன்படும் மூன்று கோண முட்டைவடிவப் பசுங்காய்கள், நெருப்பு மூட்டம் மேல் கட்டப்படும் மூங்கில் உலர்த்துப் பரண்கள் மற்றும் மெழுகுசீலை வாய் கட்டிய மண்பாண்டப் பரணி சேமிப்புக் கலங்கள்.",
    "sources": [
      "Kurunthogai 288",
      "Malaipadukadam 510-525",
      "Archaeological Survey of Western Ghats Spice Sites"
    ],
    "content": "---\nslug: artifact-green-cardamom-seed-capsules-woven-bamboo-drying-racks-and-earthen-storage-bharani\ncategory: artifact\nname_en: Green Cardamom Seed Capsules, Woven Bamboo Drying Racks & Earthen Storage Bharani\nname_ta: பசுமை ஏலக்காய் நெற்றுகள், பின்னல் மூங்கில் பரண்கள் மற்றும் மண்பாண்ட ஏலக்காய் பரணி\nera: Sangam Era to Modern Era\nyear_start: -300\nyear_end: 2026\nthinai: kurinji\nsummary_en: The physical apparatus of Tamil cardamom handling: three-sided oval green capsules with resinous black aromatic seeds, multi-tiered woven bamboo drying slats (paranai) hung above curing embers, and glazed earthenware storage jars (bharani) sealed with beeswaxed linen to preserve volatile oils.\nsummary_ta: தமிழ் மலைப்பகுதி ஏலக்காய் பதனிடப் பயன்படும் மூன்று கோண முட்டைவடிவப் பசுங்காய்கள், நெருப்பு மூட்டம் மேல் கட்டப்படும் மூங்கில் உலர்த்துப் பரண்கள் மற்றும் மெழுகுசீலை வாய் கட்டிய மண்பாண்டப் பரணி சேமிப்புக் கலங்கள்.\nsources:\n  - Kurunthogai 288\n  - Malaipadukadam 510-525\n  - Archaeological Survey of Western Ghats Spice Sites\n---\n\n# Green Cardamom Seed Capsules, Woven Bamboo Drying Racks & Earthen Storage Bharani\n\nThe material artifacts associated with cardamom agriculture showcase an intricate balance between natural botanical properties and traditional conservation materials.\n\n### 1. Green Cardamom Capsules (*பச்சை ஏலக்காய் நெற்றுகள்*)\n- Morphologically, the capsule is an inferior, trilocular, sub-globose or ovate pod (1 to 2 cm long) containing 15 to 20 angular, rugose, dark-brown seeds coated with a thin mucilaginous aril.\n- Ancient grading classified capsules into *Alleppey Green Bold* (bold 7-8 mm ribbed pods with rich green hue) and smaller pale forest collections (*nattu elakkai*).\n\n### 2. Multi-Tiered Bamboo Drying Racks (*மூங்கில் பரண் / Paranai*)\n- Constructed from split *Bambusa bambos* laths woven into open mesh lattices, these drying racks allowed uniform vertical convection.\n- Racks were stacked 4 to 6 tiers high inside curing shacks, rotated manually every 4 hours so upper and lower tiers received identical heat exposure without charring.\n\n### 3. Glazed Ceramic Storage Bharani (*சீனாக்களிமண் ஏலக்காய் பரணி*)\n- Cured cardamom absorbs atmospheric moisture rapidly, causing mould growth and turning emerald shells into dull yellow-grey.\n- Tamil spice merchants stored cured pods in thick-walled, leadless glazed ceramic jars (*bharani*) or beeswax-lined terracotta containers (*erichal poti*).\n- Jars were wrapped in dried plantain leaf sheaves (*vaazhai-chattal*) and sealed with beeswaxed cotton cloth (*mezhugu cheelai*) to form an airtight moisture and aroma barrier.\n"
  },
  {
    "slug": "artifact-pan-supari-elakkai-spice-caskets-siddha-cardamom-decoction-brass-vessels-and-pestles",
    "file": "artifact-pan-supari-elakkai-spice-caskets-siddha-cardamom-decoction-brass-vessels-and-pestles.md",
    "category": "artifact",
    "name_en": "Pan-Supari Elakkai Spice Caskets, Siddha Cardamom Decoction Brass Vessels & Pestles",
    "name_ta": "தாம்பூல ஏலக்காய் பேழைகள், சித்த ஏலக் கஷாய வெண்கலப் பாத்திரங்கள் மற்றும் உரல்கள்",
    "era": "Medieval Chola to Modern Era",
    "year_start": 850,
    "year_end": 2026,
    "thinai": "marutham",
    "summary_en": "Courtly and medical brassware: compartmentalized brass and silver betel-spice caskets (thambula petti) with dedicated cardamom chambers, heavy bronze grinding mortars (oral) designed to crush seeds without sparks, and double-rimmed brass decoction vessels used for royal digestive brews.",
    "summary_ta": "ஏலக்காய் வைக்க பிரத்யேக அறை கொண்ட பித்தளை மற்றும் வெள்ளி தாம்பூலப் பேழைகள், உராய்வுத் தீப்பொறியின்றி விதைகளை அரைக்கும் வெண்கல உரல்கள் மற்றும் அரண்மனை செரிமானக் குடிநீர் காய்ச்சும் பித்தளைப் பாத்திரங்கள்.",
    "sources": [
      "Tanjore Royal Saraswathi Mahal Craft Catalogues",
      "Chola Palace Inscriptions of Pazhaiyarai",
      "South Indian Metal Ware Excavations"
    ],
    "content": "---\nslug: artifact-pan-supari-elakkai-spice-caskets-siddha-cardamom-decoction-brass-vessels-and-pestles\ncategory: artifact\nname_en: Pan-Supari Elakkai Spice Caskets, Siddha Cardamom Decoction Brass Vessels & Pestles\nname_ta: தாம்பூல ஏலக்காய் பேழைகள், சித்த ஏலக் கஷாய வெண்கலப் பாத்திரங்கள் மற்றும் உரல்கள்\nera: Medieval Chola to Modern Era\nyear_start: 850\nyear_end: 2026\nthinai: marutham\nsummary_en: Courtly and medical brassware: compartmentalized brass and silver betel-spice caskets (thambula petti) with dedicated cardamom chambers, heavy bronze grinding mortars (oral) designed to crush seeds without sparks, and double-rimmed brass decoction vessels used for royal digestive brews.\nsummary_ta: ஏலக்காய் வைக்க பிரத்யேக அறை கொண்ட பித்தளை மற்றும் வெள்ளி தாம்பூலப் பேழைகள், உராய்வுத் தீப்பொறியின்றி விதைகளை அரைக்கும் வெண்கல உரல்கள் மற்றும் அரண்மனை செரிமானக் குடிநீர் காய்ச்சும் பித்தளைப் பாத்திரங்கள்.\nsources:\n  - Tanjore Royal Saraswathi Mahal Craft Catalogues\n  - Chola Palace Inscriptions of Pazhaiyarai\n  - South Indian Metal Ware Excavations\n---\n\n# Pan-Supari Elakkai Spice Caskets, Siddha Cardamom Decoction Brass Vessels & Pestles\n\nCardamom was deeply interwoven into courtly hospitality, ritual feasting, and medical administration throughout Tamil history, generating specialized metallurgical implements.\n\n### 1. Compartmentalized Thambula Caskets (*தாம்பூலப் பெட்டி*)\n- Aristocratic and royal households in Thanjavur, Madurai, and Gangaikondacholapuram commissioned octagonal and floral brass, bell-metal, and silver boxes (*chellam* / தாம்பூலப் பேழை).\n- The central chamber was reserved for dried areca nut, surrounded by radial compartments for betel leaf, edible camphor (*pachai karpooram*), cloves (*kirambu*), and premium green cardamom capsules.\n- Cardamom was crushed between the fingertips and tucked inside the betel-quid fold (*vetrilai-madippu*) to perfume the breath and aid post-prandial digestion.\n\n### 2. Low-Friction Bronze Pestles & Mortars (*வெண்கல உரல்*)\n- Pharmacists used bell-metal (*vengalam*) alloy mortars rather than iron, preventing metallic taint and bitter catalytic oxidation.\n- The mortar base was designed with a concave spherical depression allowing smooth circular rolling of the bronze pestle, crushing seed pericarps without heating the essential oil droplets.\n\n### 3. Herbal Decoction Cauldrons (*ஏலக் கஷாயப் பாத்திரம்*)\n- For temple feasts (*prasadam*) and hospital dispensaries (*aathula-saalai*), wide-mouthed brass cooking cauldrons (*uruLi*) with tin-lined interiors (*eeyam poosal*) were used to boil cardamom infusions, avoiding acidic reactions between spice tannins and metal substrates.\n"
  },
  {
    "slug": "concept-alpha-terpinyl-acetate-and-1-8-cineole-ester-terpene-aroma-chemistry-and-carminative-bioactivity",
    "file": "concept-alpha-terpinyl-acetate-and-1-8-cineole-ester-terpene-aroma-chemistry-and-carminative-bioactivity.md",
    "category": "concept",
    "name_en": "Alpha-Terpinyl Acetate & 1,8-Cineole Ester-Terpene Aroma Chemistry & Carminative Bioactivity",
    "name_ta": "ஆல்ஃபா-டெர்பினைல் அசிட்டேட் மற்றும் 1,8-சினியோல் நறுமண வேதியியல் மற்றும் செரிமானத் தூண்டல்",
    "era": "Sangam Era to Modern Era",
    "year_start": -300,
    "year_end": 2026,
    "thinai": "kurinji",
    "summary_en": "The phytochemistry of Elettaria cardamomum: the balanced synergy between alpha-terpinyl acetate (providing sweet, fruity, flowery notes) and 1,8-cineole (eucalyptol, providing cool camphoraceous camphoric punch), their gastric mucosal mucin secretion stimulation, smooth-muscle spasmolytic relaxation, and gastrointestinal anti-ulcerogenic efficacy.",
    "summary_ta": "ஏலக்காயின் வேதியியல் கலவை: ஆல்ஃபா-டெர்பினைல் அசிட்டேட்டின் மலர் நறுமணமும் 1,8-சினியோலின் கற்பூரக் குளிர்ச்சியும் தரும் தனித்துவச் சேர்க்கை, இரைப்பைச் சளிப்படலப் பாதுகாப்பு மற்றும் குடல் தசைப்பிடிப்பு நீக்கும் மருந்தியல் செயலாக்கம்.",
    "sources": [
      "Journal of Agricultural and Food Chemistry: Cardamom Terpenes",
      "Indian Journal of Traditional Knowledge: Siddha Spices",
      "Phytomedicine Research on Elettaria Cardamomum"
    ],
    "content": "---\nslug: concept-alpha-terpinyl-acetate-and-1-8-cineole-ester-terpene-aroma-chemistry-and-carminative-bioactivity\ncategory: concept\nname_en: Alpha-Terpinyl Acetate & 1,8-Cineole Ester-Terpene Aroma Chemistry & Carminative Bioactivity\nname_ta: ஆல்ஃபா-டெர்பினைல் அசிட்டேட் மற்றும் 1,8-சினியோல் நறுமண வேதியியல் மற்றும் செரிமானத் தூண்டல்\nera: Sangam Era to Modern Era\nyear_start: -300\nyear_end: 2026\nthinai: kurinji\nsummary_en: The phytochemistry of Elettaria cardamomum: the balanced synergy between alpha-terpinyl acetate (providing sweet, fruity, flowery notes) and 1,8-cineole (eucalyptol, providing cool camphoraceous camphoric punch), their gastric mucosal mucin secretion stimulation, smooth-muscle spasmolytic relaxation, and gastrointestinal anti-ulcerogenic efficacy.\nsummary_ta: ஏலக்காயின் வேதியியல் கலவை: ஆல்ஃபா-டெர்பினைல் அசிட்டேட்டின் மலர் நறுமணமும் 1,8-சினியோலின் கற்பூரக் குளிர்ச்சியும் தரும் தனித்துவச் சேர்க்கை, இரைப்பைச் சளிப்படலப் பாதுகாப்பு மற்றும் குடல் தசைப்பிடிப்பு நீக்கும் மருந்தியல் செயலாக்கம்.\nsources:\n  - Journal of Agricultural and Food Chemistry: Cardamom Terpenes\n  - Indian Journal of Traditional Knowledge: Siddha Spices\n  - Phytomedicine Research on Elettaria Cardamomum\n---\n\n# Alpha-Terpinyl Acetate & 1,8-Cineole Ester-Terpene Aroma Chemistry & Carminative Bioactivity\n\nThe distinctive sensory and medicinal virtues of Indian cardamom (*Elettaria cardamomum Maton*) reside in the 6 to 10 percent volatile essential oil stored inside the parenchymal cells of the inner seed coat.\n\n### 1. Dual Biochemical Signature\n- The essence of genuine green cardamom is governed by a precise natural ratio between two primary volatile constituents:\n  1. **Alpha-Terpinyl Acetate (30-45%)**: An ester giving cardamom its delicate, floral, sweet, and balsamic character.\n  2. **1,8-Cineole / Eucalyptol (25-35%)**: A cyclic ether monoterpenoid providing penetrating freshness, cooling camphoraceous pungency, and respiratory bronchodilation.\n- Minor complementary monoterpenes include linalool, linalyl acetate, sabinene, limonene, and alpha-terpineol. High-altitude Western Ghats clones maintain higher alpha-terpinyl acetate and lower harsh cineole, creating a sweeter culinary profile compared to wild sub-types.\n\n### 2. Gastrointestinal Carminative Action\n- Ingested cardamom stimulates the gustatory and olfactory receptors, triggering cephalic phase reflex secretions of salivary amylase, gastric hydrochloric acid, and pepsin.\n- In the intestine, alpha-terpinyl acetate exerts direct spasmolytic activity on gastrointestinal smooth muscle by modulating intracellular calcium ion flux, easing colic cramping and post-prandial flatulence (*vayinru porumal* / வயிற்றுப் பொருமல்).\n\n### 3. Gastric Cytoprotective & Anti-Ulcerogenic Efficacy\n- Research demonstrates that cardamom essential oil promotes gastric mucosal prostaglandin synthesis, increasing the thickness and bicarbonate concentration of the mucosal barrier against erosive acid and spicy capsicum damage.\n"
  },
  {
    "slug": "concept-sangam-high-altitude-kurinji-spicery-cardamom-hills-ecology-and-forest-gathering-tenure",
    "file": "concept-sangam-high-altitude-kurinji-spicery-cardamom-hills-ecology-and-forest-gathering-tenure.md",
    "category": "concept",
    "name_en": "Sangam High-Altitude Kurinji Spicery, Cardamom Hills Ecology & Forest Gathering Tenure",
    "name_ta": "சங்க காலக் குறிஞ்சி உயர்நில நறுமணவியல், ஏலக்காய் மலைச் சூழலியல் மற்றும் காட்டுரிமை முறை",
    "era": "Sangam Era",
    "year_start": -300,
    "year_end": 300,
    "thinai": "kurinji",
    "summary_en": "The social and environmental ecology of the Cardamom Hills (Elamalai) in classical Tamil literature: forest gathering tenure under Kurinji mountain chieftains (Velir), co-existence with elephant and tiger migration corridors, seasonal harvest camps, and bartering hill spices for lowland coastal salt and grain.",
    "summary_ta": "சங்க இலக்கியத்தில் ஏலக்காய் மலைத்தொடர் (ஏலமலை) காட்டியல் சூழல்: வேளிர் தலைவர்களின் ஆளுகைக்குட்பட்ட குறிஞ்சிப் பழங்குடிகளின் ஏல அறுவடை உரிமை, யானை வழித்தடப் பாதுகாப்பு மற்றும் உப்பு-தானிய பண்டமாற்றுப் பொருளாதார முறைமை.",
    "sources": [
      "Pathitruppathu 11",
      "Malaipadukadam 150-180",
      "Akananuru 2",
      "Historical Geography of the Western Ghats"
    ],
    "content": "---\nslug: concept-sangam-high-altitude-kurinji-spicery-cardamom-hills-ecology-and-forest-gathering-tenure\ncategory: concept\nname_en: Sangam High-Altitude Kurinji Spicery, Cardamom Hills Ecology & Forest Gathering Tenure\nname_ta: சங்க காலக் குறிஞ்சி உயர்நில நறுமணவியல், ஏலக்காய் மலைச் சூழலியல் மற்றும் காட்டுரிமை முறை\nera: Sangam Era\nyear_start: -300\nyear_end: 300\nthinai: kurinji\nsummary_en: The social and environmental ecology of the Cardamom Hills (Elamalai) in classical Tamil literature: forest gathering tenure under Kurinji mountain chieftains (Velir), co-existence with elephant and tiger migration corridors, seasonal harvest camps, and bartering hill spices for lowland coastal salt and grain.\nsummary_ta: சங்க இலக்கியத்தில் ஏலக்காய் மலைத்தொடர் (ஏலமலை) காட்டியல் சூழல்: வேளிர் தலைவர்களின் ஆளுகைக்குட்பட்ட குறிஞ்சிப் பழங்குடிகளின் ஏல அறுவடை உரிமை, யானை வழித்தடப் பாதுகாப்பு மற்றும் உப்பு-தானிய பண்டமாற்றுப் பொருளாதார முறைமை.\nsources:\n  - Pathitruppathu 11\n  - Malaipadukadam 150-180\n  - Akananuru 2\n  - Historical Geography of the Western Ghats\n---\n\n# Sangam High-Altitude Kurinji Spicery, Cardamom Hills Ecology & Forest Gathering Tenure\n\nIn the Sangam landscape taxonomy (*thinai*), the montane tracts (*Kurinji*) were renowned as the treasury of aromatic riches, where wild and managed spices flourished amid mist-shrouded peaks (*panimalai*).\n\n### 1. Elamalai in Sangam Geography\n- The southern portion of the Western Ghats was explicitly recorded as the Cardamom Range (*Elamalai* / ஏலமலை). Classical poems celebrate how mountain streams tumbled past roots of wild cardamom plants, infusing the water with spice fragrance (*ஏல நாறும் இருங்குன்றம்*).\n- Mountain chieftains (*Velir*, including rulers of the Ay, Pari, and Began lineages) controlled the mountain passes (*kanavay*) connecting the Tamil interior with the Arabian Sea coast.\n\n### 2. Forest Gathering Tenure (*காட்டுரிமை*)\n- The collection of wild forest cardamom was the customary domain of indigenous hill communities (Kanikkar, Muthuvan, and Malai Vedars).\n- Forest clans maintained traditional tenure boundaries over specified valleys (*kollai*) and practiced regenerative harvesting: leaving sufficient seeding plants to regenerate the understory.\n- Harvesting occurred under watchmen on tree platforms (*paran*) built to guard against wild elephants (*aanai*) and boars that frequented cardamom clumps during harvest season.\n\n### 3. Upland-Lowland Barter Circuit\n- Cardamom was a vital exchange commodity in the symbiotic *marutham-kurinji-neithal* network.\n- Hill clans carried bags of sun-dried cardamom, black pepper, and bamboo rice down to piedmont exchange marts, bartering them directly for sea salt (*uppu*) brought inland by Umanar salt-merchants and fine paddy grain from river delta agriculturalists.\n"
  },
  {
    "slug": "concept-siddha-elathi-sooranam-cooling-digestive-tridosha-equilibrium-and-oral-microbiome-hygiene",
    "file": "concept-siddha-elathi-sooranam-cooling-digestive-tridosha-equilibrium-and-oral-microbiome-hygiene.md",
    "category": "concept",
    "name_en": "Siddha Elathi Sooranam Cooling Digestive, Tridosha Equilibrium & Oral Microbiome Hygiene",
    "name_ta": "சித்த ஏலாதிச் சூரணம், உடல் குளிர்ச்சி, முக்குற்ற சமநிலை மற்றும் வாய் நுண்ணுயிர் தூய்மை",
    "era": "Medieval to Modern Era",
    "year_start": 600,
    "year_end": 2026,
    "thinai": "marutham",
    "summary_en": "Siddha medical principles governing cardamom: its cooling potency (seetha veeryam) mitigating aggravated Pitta heat, stabilizing digestion without overheating gastric agni, breath purification via antimicrobial action against Streptococcus mutans and anaerobic oral pathogens, and ocular tonic properties.",
    "summary_ta": "சித்த மருத்துவத்தில் ஏலக்காயின் பங்கு: பித்த சூட்டைத் தணிக்கும் சீத வீரியம், அக்னியை மிகுக்காமல் செரிமானத்தை ஒழுங்குபடுத்துதல், வாய் நாற்றம் மற்றும் நுண்ணுயிரிகளை அழிக்கும் கிருமிநாசினித் தன்மை மற்றும் கண் குளிர்ச்சி.",
    "sources": [
      "Pathartha Guna Chinthamani",
      "Siddha Materia Medica",
      "Archives of Oral Biology: Cardamom Extracts"
    ],
    "content": "---\nslug: concept-siddha-elathi-sooranam-cooling-digestive-tridosha-equilibrium-and-oral-microbiome-hygiene\ncategory: concept\nname_en: Siddha Elathi Sooranam Cooling Digestive, Tridosha Equilibrium & Oral Microbiome Hygiene\nname_ta: சித்த ஏலாதிச் சூரணம், உடல் குளிர்ச்சி, முக்குற்ற சமநிலை மற்றும் வாய் நுண்ணுயிர் தூய்மை\nera: Medieval to Modern Era\nyear_start: 600\nyear_end: 2026\nthinai: marutham\nsummary_en: Siddha medical principles governing cardamom: its cooling potency (seetha veeryam) mitigating aggravated Pitta heat, stabilizing digestion without overheating gastric agni, breath purification via antimicrobial action against Streptococcus mutans and anaerobic oral pathogens, and ocular tonic properties.\nsummary_ta: சித்த மருத்துவத்தில் ஏலக்காயின் பங்கு: பித்த சூட்டைத் தணிக்கும் சீத வீரியம், அக்னியை மிகுக்காமல் செரிமானத்தை ஒழுங்குபடுத்துதல், வாய் நாற்றம் மற்றும் நுண்ணுயிரிகளை அழிக்கும் கிருமிநாசினித் தன்மை மற்றும் கண் குளிர்ச்சி.\nsources:\n  - Pathartha Guna Chinthamani\n  - Siddha Materia Medica\n  - Archives of Oral Biology: Cardamom Extracts\n---\n\n# Siddha Elathi Sooranam Cooling Digestive, Tridosha Equilibrium & Oral Microbiome Hygiene\n\nIn the Siddha medical system of ancient Tamilakam, spices are systematically classified by their taste (*suvai*), post-digestive transformation (*pirivu*), and potency (*veeryam*). Cardamom occupies a unique category as an aromatic digestive that cools rather than overheats.\n\n### 1. Tridosha Harmonization (*முக்குற்ற சமநிலை*)\n- Unlike black pepper and dry ginger which are intensely heating (*ushna veeryam*), cardamom is regarded as sweet-pungent with cooling post-digestive action (*madhura-katu seetha veeryam*).\n- Consequently, it pacifies aggravated **Pitta** (excess internal bile, body heat, and gastric acidity) while its volatile aromatics disperse sluggish **Kapha** (mucus in lungs and throat) and ease **Vata** flatulence in the lower gut.\n- Classical verse from *Pathartha Guna Chinthamani*:\n  > *\"ஏலமது பித்தமந்தம் எரிகுன்மம் நீக்கிடுமே...\"*  \n  *(Cardamom alleviates Pitta sluggishness, burning dyspepsia, and chronic colics).*\n\n### 2. Oral Microbiome & Breath Purification (*வாய் மணம் பெருக்கல்*)\n- Chewing raw cardamom seeds was the universal breath freshener (*muka-vaasanai*) of Tamil society.\n- Pharmacological analysis confirms that cardamom essential oil exhibits strong bactericidal activity against *Streptococcus mutans*, *Porphyromonas gingivalis*, and anaerobic volatile sulphur-producing oral bacteria responsible for periodontal inflammation and halitosis.\n\n### 3. Neuro-Sensory & Ophthalmic Benefits\n- In Siddha practice, regular micro-dosing of cardamom powder mixed with cow's ghee or raw cane sugar is prescribed as a cooling eye tonic (*nethira kulirchi*) and mild sedative for mental agitated nervous strain.\n"
  },
  {
    "slug": "institution-ancient-kurinji-kudi-hill-tribe-foragers-and-bodinayakkanur-cardamom-mercantile-guilds",
    "file": "institution-ancient-kurinji-kudi-hill-tribe-foragers-and-bodinayakkanur-cardamom-mercantile-guilds.md",
    "category": "institution",
    "name_en": "Ancient Kurinji-Kudi Hill-Tribe Foragers & Bodinayakkanur Cardamom Mercantile Guilds",
    "name_ta": "பண்டைக் குறிஞ்சிக் குடிப் பழங்குடி அறுவடையாளர் மற்றும் போடிநாயக்கனூர் ஏலக்காய் வணிகச் சங்கம்",
    "era": "Medieval Era to Modern Era",
    "year_start": 1000,
    "year_end": 2026,
    "thinai": "kurinji",
    "summary_en": "The institutional ecosystem spanning tribal forest harvest communities and lowland mercantile brokers: the transition of Bodinayakkanur (Cardamom City of India) into the primary spice assembly mart, where guild auction networks, commission mandis, and trade cartels connected Western Ghats harvests to global markets.",
    "summary_ta": "மலைப்பகுதி பழங்குடி அறுவடை சமூகங்கள் மற்றும் சமவெளி ஏலக்காய் வணிகத் தரகர்களின் கூட்டு கட்டமைப்பு: இந்தியாவின் ஏலக்காய் நகரம் எனப்படும் போடிநாயக்கனூர் சந்தை, வணிகக் கூட்டமைப்புகள் மற்றும் உலகளாவிய ஏற்றுமதி இணைப்பு முறைமை.",
    "sources": [
      "Theni District Gazetteer & Epigraphs",
      "Madurai Nayaka Revenue Documents",
      "Cardamom Growers & Merchants Association Records"
    ],
    "content": "---\nslug: institution-ancient-kurinji-kudi-hill-tribe-foragers-and-bodinayakkanur-cardamom-mercantile-guilds\ncategory: institution\nname_en: Ancient Kurinji-Kudi Hill-Tribe Foragers & Bodinayakkanur Cardamom Mercantile Guilds\nname_ta: பண்டைக் குறிஞ்சிக் குடிப் பழங்குடி அறுவடையாளர் மற்றும் போடிநாயக்கனூர் ஏலக்காய் வணிகச் சங்கம்\nera: Medieval Era to Modern Era\nyear_start: 1000\nyear_end: 2026\nthinai: kurinji\nsummary_en: The institutional ecosystem spanning tribal forest harvest communities and lowland mercantile brokers: the transition of Bodinayakkanur (Cardamom City of India) into the primary spice assembly mart, where guild auction networks, commission mandis, and trade cartels connected Western Ghats harvests to global markets.\nsummary_ta: மலைப்பகுதி பழங்குடி அறுவடை சமூகங்கள் மற்றும் சமவெளி ஏலக்காய் வணிகத் தரகர்களின் கூட்டு கட்டமைப்பு: இந்தியாவின் ஏலக்காய் நகரம் எனப்படும் போடிநாயக்கனூர் சந்தை, வணிகக் கூட்டமைப்புகள் மற்றும் உலகளாவிய ஏற்றுமதி இணைப்பு முறைமை.\",\nsources:\n  - Theni District Gazetteer & Epigraphs\n  - Madurai Nayaka Revenue Documents\n  - Cardamom Growers & Merchants Association Records\n---\n\n# Ancient Kurinji-Kudi Hill-Tribe Foragers & Bodinayakkanur Cardamom Mercantile Guilds\n\nThe cardamom economic continuum was sustained by a multi-century institutional partnership bridging upland tribal harvesters, smallholder mountain planters, and lowland merchant cartels.\n\n### 1. Indigenous Foraging Guilds (*குறிஞ்சிக் குடி*)\n- Upland forest communities (Muthuvan, Paliyar, Mannan) held ancestral knowledge of wild cardamom pockets along the High Wavy Mountains and Periyar catchments.\n- Clan elders (*Kani*) negotiated harvest rights with regional chieftains and early zamindars, receiving customary guarantees of salt, handloom cloth, and iron implements in return for delivered spice tributes.\n\n### 2. Rise of the Bodinayakkanur Mart (*போடிநாயக்கனூர் ஏலக்காய் மண்டிகள்*)\n- Situated at the eastern foot of the Western Ghats pass leading to Munnar and Devikulam, Bodinayakkanur developed into the preeminent cardamom clearinghouse of peninsular India—eventually earning the title **Cardamom City of South India**.\n- Mule pack trains (*pothi-maadu*) descended the steep mountain bridle paths carrying jute gunny bags of green cured pods to Bodinayakkanur commission mandis.\n\n### 3. Mercantile Auction Networks & Quality Grading\n- Bodinayakkanur merchant guilds pioneered structured closed-bid auction mechanisms (*kodi-kattu* / கைக்குட்டை முறை) where commission agents evaluated aroma, seed color, and pod size under concealed hand signals.\n- The guild established standardized weight scales (*thookku*), grading protocols (Bleached, Extra Bold, Super Bold), and credit advances to growers that buffered high-altitude agricultural volatility across centuries.\n"
  },
  {
    "slug": "place-bodinayakkanur-ancient-western-ghats-elakkai-cardamom-spicery-haven",
    "file": "place-bodinayakkanur-ancient-western-ghats-elakkai-cardamom-spicery-haven.md",
    "category": "place",
    "name_en": "Bodinayakkanur: Ancient Western Ghats Elakkai Cardamom Spicery Haven",
    "name_ta": "போடிநாயக்கனூர்: மேற்குத் தொடர்ச்சி மலை ஏலக்காய் மற்றும் நறுமணப் பெருநகரம்",
    "era": "Medieval to Modern Era",
    "year_start": 800,
    "year_end": 2026,
    "thinai": "kurinji",
    "summary_en": "Geographical and historical profile of Bodinayakkanur in the foothills of the Cardamom Hills (Theni district, Tamil Nadu): the epicentre of South Indian cardamom commerce, commanding historic mountain ghat roads, warehousing complexes, and export pipelines.",
    "summary_ta": "ஏலக்காய் மலையின் அடிவாரத்தில் அமைந்துள்ள போடிநாயக்கனூர் (தேனி மாவட்டம்) நகரத்தின் புவியியல் மற்றும் வரலாற்றுப் பின்னணி: தென்னிந்திய ஏலக்காய் வர்த்தகத்தின் தாயகம், மலைப்பாதை வணிக வழித்தடங்கள் மற்றும் கிடங்குகளின் தலைமை மையம்.",
    "sources": [
      "Theni Archaeological Inscriptions",
      "Madurai District Manual by J.H. Nelson",
      "Spices Board Auction Centre Records"
    ],
    "content": "---\nslug: place-bodinayakkanur-ancient-western-ghats-elakkai-cardamom-spicery-haven\ncategory: place\nname_en: Bodinayakkanur: Ancient Western Ghats Elakkai Cardamom Spicery Haven\nname_ta: போடிநாயக்கனூர்: மேற்குத் தொடர்ச்சி மலை ஏலக்காய் மற்றும் நறுமணப் பெருநகரம்\nera: Medieval to Modern Era\nyear_start: 800\nyear_end: 2026\nthinai: kurinji\nsummary_en: Geographical and historical profile of Bodinayakkanur in the foothills of the Cardamom Hills (Theni district, Tamil Nadu): the epicentre of South Indian cardamom commerce, commanding historic mountain ghat roads, warehousing complexes, and export pipelines.\nsummary_ta: ஏலக்காய் மலையின் அடிவாரத்தில் அமைந்துள்ள போடிநாயக்கனூர் (தேனி மாவட்டம்) நகரத்தின் புவியியல் மற்றும் வரலாற்றுப் பின்னணி: தென்னிந்திய ஏலக்காய் வர்த்தகத்தின் தாயகம், மலைப்பாதை வணிக வழித்தடங்கள் மற்றும் கிடங்குகளின் தலைமை மையம்.\nsources:\n  - Theni Archaeological Inscriptions\n  - Madurai District Manual by J.H. Nelson\n  - Spices Board Auction Centre Records\n---\n\n# Bodinayakkanur: Ancient Western Ghats Elakkai Cardamom Spicery Haven\n\n**Coordinates:** `10.0104° N, 77.3486° E`  \n**Landscape Ecosystem:** High-altitude mountain foothills (*Kurinji-Mullai transitional zone*)  \n**Modern District:** Theni District, Tamil Nadu  \n\n### 1. Strategic Mountain Gateway\n- Bodinayakkanur lies nested at the foot of the Anamalai and Cardamom Hills massif, nestled inside a scenic mountain amphitheatre fed by the Kottagudi River.\n- The town controls the ancient Kurangani and Bodimettu mountain passes that climb through dense shola forests into the high-elevation cardamom estates of Idukki and the Peerumedu plateaus.\n\n### 2. Commercial Hub of the Spice World\n- For centuries, Bodinayakkanur served as the primary assembly depot where mountain harvest meets inter-state transport. Over 70 percent of India's green cardamom production is traditionally processed, graded, auctioned, and dispatched through Bodinayakkanur mandis.\n- The town developed extensive spice warehouses designed with stone-flagged floors and cedar-lined interiors to insulate delicate pods against humidity.\n\n### 3. Cultural & Architectural Heritage\n- The historic Bodinayakkanur Zamin Palace, temples, and bustling spice streets (*Elakkai Mandi Veethi*) retain centuries of trading lore, where family firms have maintained export ledgers reaching Persian Gulf ports, Mediterranean emporia, and Southeast Asian capitals.\n"
  },
  {
    "slug": "text-sangam-anthologies-and-siddha-elathi-classics-on-fragrant-cardamom-tributes",
    "file": "text-sangam-anthologies-and-siddha-elathi-classics-on-fragrant-cardamom-tributes.md",
    "category": "text",
    "name_en": "Sangam Anthologies & Siddha Elathi Classics on Fragrant Cardamom Tributes",
    "name_ta": "சங்க இலக்கியங்கள் மற்றும் ஏலாதி நீதி நூல் காட்டும் நறுமண ஏலக்காய்ப் பதிவுகள்",
    "era": "Sangam to Post-Sangam Era",
    "year_start": -200,
    "year_end": 700,
    "thinai": "kurinji",
    "summary_en": "Epigraphical and literary references to cardamom in classical Tamil corpora: Pathitruppathu descriptions of Chera mountain tributes, Akananuru descriptions of forest fragrance, and the naming of the post-Sangam moral classic Elathi after the six-spice medicinal compound led by cardamom.",
    "summary_ta": "செவ்வியல் தமிழ் இலக்கியங்களில் ஏலக்காய் பதிவுகள்: பதிற்றுப்பத்தில் சேர மன்னர்களுக்குக் கிடைத்த ஏலமலை நறுமணத் திறைகள், அகநானூற்றுப் பாடல்கள் மற்றும் ஏலத்தை முதன்மையாகக் கொண்ட பதினெண்கீழ்க்கணக்கு நூலான ஏலாதி.",
    "sources": [
      "Pathitruppathu 11 (Cheran Senguttuvan)",
      "Elathi by Kanimethaviyar",
      "Silappadikaram: Kaadu Kaan Kaathai"
    ],
    "content": "---\nslug: text-sangam-anthologies-and-siddha-elathi-classics-on-fragrant-cardamom-tributes\ncategory: text\nname_en: Sangam Anthologies & Siddha Elathi Classics on Fragrant Cardamom Tributes\nname_ta: சங்க இலக்கியங்கள் மற்றும் ஏலாதி நீதி நூல் காட்டும் நறுமண ஏலக்காய்ப் பதிவுகள்\nera: Sangam to Post-Sangam Era\nyear_start: -200\nyear_end: 700\nthinai: kurinji\nsummary_en: Epigraphical and literary references to cardamom in classical Tamil corpora: Pathitruppathu descriptions of Chera mountain tributes, Akananuru descriptions of forest fragrance, and the naming of the post-Sangam moral classic Elathi after the six-spice medicinal compound led by cardamom.\nsummary_ta: செவ்வியல் தமிழ் இலக்கியங்களில் ஏலக்காய் பதிவுகள்: பதிற்றுப்பத்தில் சேர மன்னர்களுக்குக் கிடைத்த ஏலமலை நறுமணத் திறைகள், அகநானூற்றுப் பாடல்கள் மற்றும் ஏலத்தை முதன்மையாகக் கொண்ட பதினெண்கீழ்க்கணக்கு நூலான ஏலாதி.\nsources:\n  - Pathitruppathu 11 (Cheran Senguttuvan)\n  - Elathi by Kanimethaviyar\n  - Silappadikaram: Kaadu Kaan Kaathai\n---\n\n# Sangam Anthologies & Siddha Elathi Classics on Fragrant Cardamom Tributes\n\nCardamom occupies a revered status in ancient Tamil poetry and moral literature, symbolizing supreme aromatic elegance, upland prosperity, and healing virtues.\n\n### 1. Sangam Upland Tributes in Pathitruppathu\n- In the Chera dynastic anthology *Pathitruppathu*, the great poet Paranar describes the bounties of the Western Ghats under Cheran Senguttuvan:\n  > *\"மணம் கமழ் ஏலமும் மிளகும்...\"*  \n  *(Sweetly perfumed cardamom pods and black pepper vines flourishing together along precipitous mountain crags).*\n- Cardamom was collected by the mountain clans as royal tribute and brought to the seaport of Musiris (Kodungallur) where foreign ships waited.\n\n### 2. Silappadikaram on Courtly Aromatics\n- In Ilango Adigal's *Silappadikaram*, when describing the royal cosmetic pastes and fragrant waters prepared for Kannagi and Kovalan in Poompuhar, cardamom (*Elam*) is listed as the essential head-note of the thirty-two aromatic bathing powders (*Muppattirandu Vagai Vasanai Sooranam*).\n\n### 3. The Moral Classic: Elathi (*ஏலாதி*)\n- Among the Eighteen Lesser Texts (*Pathinenkilkanakku*), the didactic work *Elathi* composed by Kanimethaviyar takes its very title from the pharmacological formula led by cardamom.\n- Just as the compound of six ingredients—Cardamom (*Elam*), Cloves (*Lavangam*), Ginger (*Sirunavarpookkal* / *Sukku*), Pepper (*Milagu*), Long Pepper (*Thippili*), and Ceylon Ironwood (*Sirunagappoo*)—eradicates disease from the physical body, each quatrain of *Elathi* imparts six moral virtues to banish spiritual ignorance from human society.\n"
  }
]

EDGES = [
  [
    "technology-elakkai-understory-agroforestry-hand-harvesting-and-curing-kiln-technology",
    "located_in",
    "place-bodinayakkanur-ancient-western-ghats-elakkai-cardamom-spicery-haven",
    "material_culture",
    "Sangam Era to Modern Era",
    "Cardamom understory curing kilns centred around Bodinayakkanur foothills",
    "Spices Board Manuals"
  ],
  [
    "technology-elakkai-understory-agroforestry-hand-harvesting-and-curing-kiln-technology",
    "utilizes_artifact",
    "artifact-green-cardamom-seed-capsules-woven-bamboo-drying-racks-and-earthen-storage-bharani",
    "material_culture",
    "Sangam Era to Modern Era",
    "Multi-tiered bamboo drying racks used in kiln curing of green cardamom",
    "Malaipadukadam"
  ],
  [
    "technology-elakkai-cardamom-essential-oil-hydrodistillation-and-siddha-carminative-compounding-technology",
    "applies_concept",
    "concept-alpha-terpinyl-acetate-and-1-8-cineole-ester-terpene-aroma-chemistry-and-carminative-bioactivity",
    "material_culture",
    "Sangam Era to Modern Era",
    "Cardamom oil distillation harnesses alpha-terpinyl acetate and 1,8-cineole terpenes",
    "Phytomedicine"
  ],
  [
    "technology-elakkai-cardamom-essential-oil-hydrodistillation-and-siddha-carminative-compounding-technology",
    "utilizes_artifact",
    "artifact-pan-supari-elakkai-spice-caskets-siddha-cardamom-decoction-brass-vessels-and-pestles",
    "material_culture",
    "Medieval Era",
    "Low-friction bronze mortars and pestles used for compounding Elathi Chooranam",
    "Saraswathi Mahal Records"
  ],
  [
    "concept-sangam-high-altitude-kurinji-spicery-cardamom-hills-ecology-and-forest-gathering-tenure",
    "manifested_at",
    "place-bodinayakkanur-ancient-western-ghats-elakkai-cardamom-spicery-haven",
    "material_culture",
    "Sangam Era",
    "Cardamom Hills ecology directly surrounds the Bodinayakkanur mountain haven",
    "Pathitruppathu 11"
  ],
  [
    "concept-sangam-high-altitude-kurinji-spicery-cardamom-hills-ecology-and-forest-gathering-tenure",
    "documented_in",
    "text-sangam-anthologies-and-siddha-elathi-classics-on-fragrant-cardamom-tributes",
    "material_culture",
    "Sangam Era",
    "Pathitruppathu and Akananuru document the Kurinji forest cardamom gathering",
    "Akananuru 2"
  ],
  [
    "concept-siddha-elathi-sooranam-cooling-digestive-tridosha-equilibrium-and-oral-microbiome-hygiene",
    "documented_in",
    "text-sangam-anthologies-and-siddha-elathi-classics-on-fragrant-cardamom-tributes",
    "material_culture",
    "Post-Sangam Era",
    "Moral classic Elathi takes its name from the cooling medicinal compound",
    "Elathi by Kanimethaviyar"
  ],
  [
    "institution-ancient-kurinji-kudi-hill-tribe-foragers-and-bodinayakkanur-cardamom-mercantile-guilds",
    "governs_place",
    "place-bodinayakkanur-ancient-western-ghats-elakkai-cardamom-spicery-haven",
    "material_culture",
    "Medieval Era to Modern Era",
    "Bodinayakkanur cardamom mercantile guilds operated the primary auction mandis",
    "Theni Gazetteer"
  ],
  [
    "institution-ancient-kurinji-kudi-hill-tribe-foragers-and-bodinayakkanur-cardamom-mercantile-guilds",
    "organizes_practice",
    "technology-elakkai-understory-agroforestry-hand-harvesting-and-curing-kiln-technology",
    "material_culture",
    "Medieval Era",
    "Kurinji-Kudi tribal foragers gathered forest cardamom for the lowland guild mandis",
    "Madurai Manual"
  ],
  [
    "artifact-pan-supari-elakkai-spice-caskets-siddha-cardamom-decoction-brass-vessels-and-pestles",
    "embodies_concept",
    "concept-siddha-elathi-sooranam-cooling-digestive-tridosha-equilibrium-and-oral-microbiome-hygiene",
    "material_culture",
    "Medieval Chola Era",
    "Thambula spice caskets served cardamom to freshen breath and balance digestion",
    "Pazhaiyarai Inscriptions"
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
