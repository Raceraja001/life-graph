#!/usr/bin/env python3
# Ingestion harvester for Batch 22 Corpus 3: Beaten Bark-Cloth Manufacture & Sizing
import os
import sys
import json
import uuid
import psycopg2
import requests

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
MOOLAM_KNOWLEDGE = "/mnt/h/DevTools/Projects/learn-ai/moolam-chronicles"

DOSSIERS = [
  {
    "file": "knowledge/texts/text-tirumurukarruppadai-hermit-bark-garments-maravuri-poetry.md",
    "slug": "text-tirumurukarruppadai-hermit-bark-garments-maravuri-poetry",
    "category": "text",
    "name_en": "Tirumurukarruppadai & Sangam Poetry on Hermit Beaten Bark Garments (Maravuri)",
    "name_ta": "திருமுருகாற்றுப்படை மரவுரி ஆடை மற்றும் முனிவர் தவவுடைப் பாடல்கள்",
    "era": "Sangam Classical Era",
    "year_start": -200,
    "year_end": 100,
    "thinai": "kurinji",
    "summary_en": "Tirumurukarruppadai lines 126-135 and Akananuru verses celebrating the ascetic garments of mountain hermits and sages: supple, beaten tree-bark garments (Maravuri) crafted from the fibrous inner bast of mountain trees, washed in mineral springs, and sun-dried to golden flexibility.",
    "summary_ta": "திருமுருகாற்றுப்படையில் விவரிக்கப்படும் மலைவாழ் முனிவர்களின் மரவுரி ஆடை நுட்பம்: மலைக் காடுகளில் மரத்தின் உள் பட்டையை உரித்து, கல்லில் தட்டி, நாரைப் பிரித்து, சுனைநீரில் அலசி உருவாக்கப்பட்ட மெல்லிய தவவுடைப் பாடல்கள்.",
    "sources": [
      "Tirumurukarruppadai 126-135",
      "Akananuru 235",
      "Purananuru 251"
    ],
    "content": "---\nid: text-tirumurukarruppadai-hermit-bark-garments-maravuri-poetry\ntitle: Tirumurukarruppadai & Sangam Poetry on Hermit Beaten Bark Garments (Maravuri)\ntype: text\nera: Sangam Classical Era (c. 200 BCE - 100 CE)\nthinai: kurinji (Ascetic Material Culture & Bast Fiber Craft)\nstatus: canonical\n---\n\n# Tirumurukarruppadai & Sangam Poetry on Hermit Beaten Bark Garments (Maravuri)\n\n## 1. Classical Descriptions of Maravuri\nIn ancient Tamil literature, before the widespread ubiquity of cultivated cotton and silk, the fibrous bast of mountain trees provided an essential textile medium. Ascetics, yogis (*Munivar*), and forest dwellers wore **Maravuri (மரவுரி)**.\n\nIn *Tirumurukarruppadai*, Nakkirar portrays the venerable ascetics arriving at Tirupparankunram:\n> \"மாசறக் கழுவிய பல்காழ் நூலொடு\n> மரவுரி உடுத்த மாணிழை முனிவர்...\"\n*(The holy sages wearing spotlessly washed sacred cords and draped in garments of beaten tree-bark).*\n\n## 2. Textual Characteristics\n1. **Supple Texture**: Unlike stiff raw wood, properly prepared *Maravuri* was described as soft, pliable, and cloth-like.\n2. **Purity and Renunciation**: Free from the animal killing associated with silk (*Pattadai*) and urban commercial weaving, bark cloth embodied absolute harmony with the forest biosphere.\n"
  },
  {
    "file": "knowledge/inscriptions/insc-sirumalai-pandya-forest-fiber-tribute-charters.md",
    "slug": "insc-sirumalai-pandya-forest-fiber-tribute-charters",
    "category": "inscription",
    "name_en": "Sirumalai Pandya Forest Bast-Fiber & Cordage Tribute Charters",
    "name_ta": "சிறுமலை பாண்டியர் காடுறை நார்ப்பொருள் மற்றும் மரவுரி வரிப் பட்டயங்கள்",
    "era": "Pandya Classical Era",
    "year_start": 750,
    "year_end": 900,
    "thinai": "kurinji",
    "summary_en": "Pandya rock inscriptions from the foothills of Sirumalai in Dindigul district recording forest tribute (Kaattu-Vari) paid by hill tribes (Kaanavar) in coils of processed tree-bast fibers, bark cordage, and beaten ascetic sheets for royal monasteries.",
    "summary_ta": "திண்டுக்கல் சிறுமலை அடிவாரக் கல்வெட்டுகள்; மலைவாழ் பழங்குடியினர் பாண்டிய மன்னருக்குக் காணிக்கையாக செலுத்திய பதப்படுத்தப்பட்ட மர நார்ப்பொருட்கள் மற்றும் துறவியர் மரவுரிப் பதிவுகள்.",
    "sources": [
      "South Indian Inscriptions Vol. XIV",
      "Dindigul Epigraphical Survey"
    ],
    "content": "---\nid: insc-sirumalai-pandya-forest-fiber-tribute-charters\ntitle: Sirumalai Pandya Forest Bast-Fiber & Cordage Tribute Charters\ntype: inscription\nera: Pandya Classical Era (c. 750 - 900 CE)\nthinai: kurinji (Forest Tribute & Agro-Forestry Epigraphy)\nstatus: canonical\n---\n\n# Sirumalai Pandya Forest Bast-Fiber & Cordage Tribute Charters\n\n## 1. Epigraphical Provenance\nThe Sirumalai hill complex, south of the Kodaganar river basin, was celebrated in Silappadikaram for its dense agro-forestry and aromatic vegetation. \n\nRock-cut inscriptions near Sanarpatti record formal arrangements between the Pandya royal treasury and the local hill chieftain (*Kaanavan*).\n\n## 2. Tribute Specifications\n- **Naaru-Padi**: Fixed annual levies of beaten *Maravuri* sheets supplied to local Jaina rock monasteries (*Palli*) for ascetics' bedding and robes.\n- **Vada-Kayiru**: Heavy rope coils twisted from inner bast fibers of *Ficus benghalensis* and *Sterculia villosa* used for temple chariot towing.\n"
  },
  {
    "file": "knowledge/inscriptions/insc-alagar-malai-jaina-cavern-bark-mat-endowment-epigraphs.md",
    "slug": "insc-alagar-malai-jaina-cavern-bark-mat-endowment-epigraphs",
    "category": "inscription",
    "name_en": "Alagar Malai Jaina Cavern Bark-Mat & Fiber Matting Endowment Epigraphs",
    "name_ta": "அழகர்மலை சமணர் குடைவரை மரவுரிப் பாய் மற்றும் நார்ப் படுக்கைக் கல்வெட்டுகள்",
    "era": "Early Historic Era",
    "year_start": -200,
    "year_end": 100,
    "thinai": "kurinji",
    "summary_en": "Early Tamil-Brahmi drip-ledge inscriptions at Alagar Malai near Madurai recording endowments of beaten bast fiber sleeping mats (Naattu-Paai / Maravuri) and ascetic garments gifted by merchant guilds to resident Jaina ascetics.",
    "summary_ta": "மதுரை அழகர்மலை சமணர் குகைக்களத்தில் பொறிக்கப்பட்ட தமிழ்-பிராமி கல்வெட்டுகள்; சமண முனிவர்களின் தவப்படுக்கைகளுக்காக வணிகர்களால் அளிக்கப்பட்ட மரவுரிப் பாய்கள் மற்றும் நார்ப் பொருட்கள் பற்றிய சான்றுகள்.",
    "sources": [
      "Mahadevan: Early Tamil Epigraphy (Alagarmalai Inscriptions)",
      "ASI Reports on Madurai Jaina Caverns"
    ],
    "content": "---\nid: insc-alagar-malai-jaina-cavern-bark-mat-endowment-epigraphs\ntitle: Alagar Malai Jaina Cavern Bark-Mat & Fiber Matting Endowment Epigraphs\ntype: inscription\nera: Early Historic Era (c. 200 BCE - 100 CE)\nthinai: kurinji (Ascetic Epigraphy & Cavern Endowments)\nstatus: canonical\n---\n\n# Alagar Malai Jaina Cavern Bark-Mat & Fiber Matting Endowment Epigraphs\n\n## 1. Context at Alagar Malai\nAlagar Malai (ancient *Tirumaliruncholai*), rising 20 km northeast of Madurai, contains extensive natural granite rock shelters equipped with chisel-cut drip ledges (*Kavadi*) and polished stone beds (*Kal-padukai*).\n\n## 2. Inscriptional Epigraphical Reading\nSeveral short Tamil-Brahmi inscriptions incised beneath the brow of the cavern record gifts by merchant donors:\n- Donors from Madurai gifting **Naaru-Padukai** (mats made of beaten inner bark fibers) to protect ascetic monks sleeping on the cold, damp granite rock beds.\n"
  },
  {
    "file": "knowledge/concepts/concept-ficus-and-antiaris-inner-bast-peeling-and-retting-mechanics.md",
    "slug": "concept-ficus-and-antiaris-inner-bast-peeling-and-retting-mechanics",
    "category": "concept",
    "name_en": "Ficus and Antiaris Inner Bast Peeling, Phloem Stripping & River Retting Mechanics",
    "name_ta": "மரப் பட்டை உரித்தல், நார்ப் படலப் பிரிப்பு மற்றும் ஆற்று நீரில் அழுகவைத்தல் நுட்பம்",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 400,
    "thinai": "kurinji",
    "summary_en": "The botanical harvesting of tree-bast fibers: stripping the fibrous secondary phloem layer from felled or living branches of Antiaris toxicaria (Upas / Mara-maram), Ficus religiosa, and Sterculia villosa, followed by prolonged steeping in running stream water to dissolve gummy pectins and isolate cellulose fiber sheets.",
    "summary_ta": "மரப்பட்டையிலிருந்து சல்லடைக்குழாய் நார்ப் படலத்தை மட்டும் உரித்தெடுத்து, ஓடும் ஆற்றுநீரில் ஊறவைத்து பெக்டின் பிசின்களைக் கரைத்து மென்மையான செல்லுலோஸ் நார்த் தாள்களைப் பிரித்தெடுக்கும் பண்டைய தாவரவியல் நுட்பம்.",
    "sources": [
      "Kooiman: Tapa in the Pacific & Asia",
      "Gamble: Manual of Indian Timbers",
      "Cardon: Natural Bast Fibers"
    ],
    "content": "---\nid: concept-ficus-and-antiaris-inner-bast-peeling-and-retting-mechanics\ntitle: Ficus and Antiaris Inner Bast Peeling, Phloem Stripping & River Retting Mechanics\ntype: concept\nera: Early Historic Era (c. 400 BCE - 400 CE)\nthinai: kurinji (Botanical Fiber Science & Agronomy)\nstatus: canonical\n---\n\n# Ficus and Antiaris Inner Bast Peeling, Phloem Stripping & River Retting Mechanics\n\n## 1. Selected Botanical Species\nNot all tree bark can produce flexible cloth. Ancient Tamil craftsmen harvested specific trees possessing long, interlaced bast fibers (phloem cells) with high tensile strength:\n- **Mara-maram / Upas (*Antiaris toxicaria*)**: The inner bark naturally separates into whole cylindrical sheets.\n- **Kattalangu (*Sterculia villosa*)**: Yields tough, white, ribbon-like bast fibers.\n- **Athi / Arasu (*Ficus racemosa / Ficus religiosa*)**: Pliable, fine-textured bark ideal for garments.\n\n## 2. Harvesting and Peeling Sequence\n1. **Circumferential Incision**: Two parallel cuts made around the trunk or straight branch at 2-meter intervals, joined by a single longitudinal slit.\n2. **Peeling**: Wooden bone spatulas gently prized the outer rough cork bark away from the underlying cream-colored fibrous inner bast (*Agatholi*).\n3. **Running-Water Retting (*Aatru-Ooruthal*)**: The stripped bast was submerged under river stones in clean mountain brooks for 3 to 5 days. Water-borne bacteria metabolized water-soluble pectins and gums, loosening the fiber bundles without rotting the cellulose.\n"
  },
  {
    "file": "knowledge/concepts/concept-grooved-hardwood-mallet-tapa-beating-and-fiber-felting-thattu-thadi.md",
    "slug": "concept-grooved-hardwood-mallet-tapa-beating-and-fiber-felting-thattu-thadi",
    "category": "concept",
    "name_en": "Grooved Hardwood Mallet Tapa Beating, Anvil Mechanical Felting & Sheet Expansion (Thattu-Thadi)",
    "name_ta": "வரிப்பள்ள மரக்கட்டை தட்டுதல், பாறைப்பட்டடை நெரித்தல் மற்றும் தாளாக்கும் இயந்திரவியல்",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 400,
    "thinai": "kurinji",
    "summary_en": "The mechanical felting of bast fibers into cloth: placing water-soaked bast strips upon smooth stone or hardwood log anvils and systematically beating them with longitudinally grooved hardwood beaters (Thattu-Thadi). The impact crushes plant cells, forces overlapping fibers to mechanically interlock, and expands narrow bark strips into broad, supple sheets.",
    "summary_ta": "நனைத்த மரப்பட்டை நார்களை வழவழப்பான பாறை மீது வைத்து, வரிப்பள்ளங்கள் கொண்ட கடின மரக்கட்டையால் (தட்டுத்தடி) அடித்து, நார்களை ஒன்றோடொன்று பிணைத்து அகலமான, நெகிழ்வான துணித் தாள்களாக மாற்றிய இயந்திரவியல் நுட்பம்.",
    "sources": [
      "Kennedy: Bark-Cloth Technology in South and Southeast Asia",
      "Archaeological Evidence for Prehistoric Tapa Beaters in India"
    ],
    "content": "---\nid: concept-grooved-hardwood-mallet-tapa-beating-and-fiber-felting-thattu-thadi\ntitle: Grooved Hardwood Mallet Tapa Beating, Anvil Mechanical Felting & Sheet Expansion (Thattu-Thadi)\ntype: concept\nera: Early Historic Era (c. 400 BCE - 400 CE)\nthinai: kurinji (Mechanical Felting & Tool Technology)\nstatus: canonical\n---\n\n# Grooved Hardwood Mallet Tapa Beating, Anvil Mechanical Felting & Sheet Expansion (Thattu-Thadi)\n\n## 1. The Beater Apparatus (*Thattu-Thadi*)\nThe primary tool of the bark-cloth artisan was a four-sided club carved from extremely dense, heavy ironwood or ebony (*Karungali*):\n- Each of the four faces was incised with parallel longitudinal grooves of varying pitch:\n  - **Coarse Grooves (5 mm pitch)**: Used in the initial phase to crush raw bark and break lignin bonds.\n  - **Fine Grooves (1.5 mm pitch)**: Used in intermediate beating to mesh microfibrils.\n  - **Smooth Face**: Used in the final pass to polish and flatten the felted sheet.\n\n## 2. Mechanical Felting Kinetics\nAs the artisan delivers rhythmic blows against the wet bast placed on a smooth granite anvil slab (*Kallu-Pattadai*):\n- The compressive shear forces flatten cylindrical phloem tubes into thin ribbons.\n- Adjacent fibers are forced into physical contact, intertwining through hydrogen bonding between cellulose hydroxyl groups.\n- A strip originally 10 cm wide expands under repeated beating to **30 to 50 cm width**, becoming soft, translucent, and cloth-like.\n"
  },
  {
    "file": "knowledge/concepts/concept-botanical-starch-sizing-and-herbal-mastic-pasai-finishing.md",
    "slug": "concept-botanical-starch-sizing-and-herbal-mastic-pasai-finishing",
    "category": "concept",
    "name_en": "Botanical Rice Starch Sizing, Tamarind Seed Gum & Herbal Mastic Finishing (Pasai)",
    "name_ta": "அரிசிக் கஞ்சி பசை பூச்சு, புளியங்கொட்டைப் பிசின் மற்றும் மூலிகை வழவழப்பு நுட்பம்",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": 500,
    "thinai": "mullai",
    "summary_en": "The chemical finishing of beaten bark sheets: saturating porous bark cloth with boiled rice congee starch (Kanchi) or tamarind kernel gum (Puliyankottai-Pasai) mixed with neem and turmeric extracts. Sizing seals fiber pores, imparts moisture resistance, prevents insect borers, and creates a smooth non-absorbent surface suitable for ink writing.",
    "summary_ta": "அடிக்கப்பட்ட மரவுரித் தாள்களின் நுண்துளைகளை அடைக்க அரிசிக் கஞ்சி, புளியங்கொட்டைப் பசை, வேப்பிலை மற்றும் மஞ்சள் சாறு சேர்த்துப் பூசுதல்; பூஞ்சை மற்றும் பூச்சிகளைத் தடுத்து எழுதுவதற்கும் உடுத்துவதற்கும் ஏற்ற வழவழப்பைத் தரும் நுட்பம்.",
    "sources": [
      "Sarma: Indigenous Paper and Writing Materials of South India",
      "Traditional Botanical Adhesives of Tamil Nadu"
    ],
    "content": "---\nid: concept-botanical-starch-sizing-and-herbal-mastic-pasai-finishing\ntitle: Botanical Rice Starch Sizing, Tamarind Seed Gum & Herbal Mastic Finishing (Pasai)\ntype: concept\nera: Early Historic Era (c. 300 BCE - 500 CE)\nthinai: mullai (Polymer Sizing & Surface Chemistry)\nstatus: canonical\n---\n\n# Botanical Rice Starch Sizing, Tamarind Seed Gum & Herbal Mastic Finishing (Pasai)\n\n## 1. Purpose of Sizing (*Pasai-Etru*)\nUnsized beaten bark cloth is hygroscopic, porous, and prone to fraying along fiber borders. \n\nTo transform felted bark sheets into durable garments or writing media, artisans applied a multi-component **botanical size**:\n\n## 2. Formulation Chemistry\n1. **Starch Hydrocolloid**: Thick boiled rice water (*Kanchi*) rich in amylose and amylopectin, or soaked and pulverized tamarind seed powder (*Puliyankottai*).\n2. **Bio-Active Insecticides**: Crushed neem leaf juice (*Veppilai-saaru*) containing azadirachtin and ground turmeric (*Manjal*) acting as natural antifungal and antibacterial preservatives.\n3. **Application & Burnishing**: The warm paste was rubbed evenly across both faces of the bark sheet with cloth balls, dried in shade, and burnished with smooth river agates (*Uraikal*) to compact the starch layer into a glossy, ink-resistant finish.\n"
  },
  {
    "file": "knowledge/concepts/concept-ascetic-hermit-bark-vestments-and-proto-paper-writing-sheets-maravuri.md",
    "slug": "concept-ascetic-hermit-bark-vestments-and-proto-paper-writing-sheets-maravuri",
    "category": "concept",
    "name_en": "Ascetic Hermit Bark Vestments, Proto-Paper Writing Surfaces & Funerary Shrouds (Maravuri)",
    "name_ta": "துறவியர் மரவுரி ஆடைகள், ஆதி காகித எழுத்துத் தாள்கள் மற்றும் ஈமப்போர்வை நுட்பம்",
    "era": "Early Historic to Medieval Era",
    "year_start": -300,
    "year_end": 1000,
    "thinai": "kurinji",
    "summary_en": "The dual utilitarian and ritual evolution of beaten bark-cloth (Maravuri): functioning as ascetic hermit garments representing forest renunciation, breathable bedding in rock shelters, funerary wrappings for chieftains, and smooth sized writing sheets for early astronomical and medical notes.",
    "summary_ta": "மரவுரித் துணியின் பன்முகப் பயன்பாடுகள்: தவ முனிவர்களின் துறவற ஆடை, குகைப் படுக்கைகள், பெருங்கற்கால ஈம உடைகள் மற்றும் பனை ஓலைகளுக்கு முந்தைய ஆதி மருத்துவக் குறிப்பு எழுத்துத் தாள்களாக விளங்கிய வரலாற்றுப் பயன்பாடு.",
    "sources": [
      "Zvelebil: The Smile of Murugan",
      "Subrahmanian: Pre-Pallava Tamil Index",
      "Mahadevan: Epigraphy & Writing Surfaces"
    ],
    "content": "---\nid: concept-ascetic-hermit-bark-vestments-and-proto-paper-writing-sheets-maravuri\ntitle: Ascetic Hermit Bark Vestments, Proto-Paper Writing Surfaces & Funerary Shrouds (Maravuri)\ntype: concept\nera: Early Historic to Medieval Era (c. 300 BCE - 1000 CE)\nthinai: kurinji (Material Culture & Early Writing Technology)\nstatus: canonical\n---\n\n# Ascetic Hermit Bark Vestments, Proto-Paper Writing Surfaces & Funerary Shrouds (Maravuri)\n\n## 1. Cultural Symbolism of the Forest Vestment\nIn Tamil society, while bleached cotton and crimson silks (*Pattu*) denoted royal luxury and urban decadence, **Maravuri** was the unassailable hallmark of sacred detachment:\n- Worn by Jain, Buddhist, and Saiva hermits inhabiting the granitic cavern hills of Pandyan and Pallava realms.\n- Highly revered for its thermal insulation: naturally warm in cold mountain winter nights and cool under summer sun.\n\n## 2. Proto-Paper Writing Sheets\nFinely beaten and starch-sized bark cloth sheets functioned as flexible writing media:\n- Charcoal and gallnut ink (*Kadukkai-mai*) painted with reed pens adhered cleanly to the sized surface without feathering.\n- Used for portable astrological horoscopes (*Jadhakam*) and herbal medicine formulas (*Vaithiya-vuri*) before the widespread adoption of palm-leaf bundles (*Olais*).\n"
  },
  {
    "file": "knowledge/characters/char-sirumalai-master-bark-cloth-beater-maravuri-thozhilan.md",
    "slug": "char-sirumalai-master-bark-cloth-beater-maravuri-thozhilan",
    "category": "character",
    "name_en": "Master Bark-Cloth Beater & Forest Textile Specialist: Maravuri Thozhilan of Sirumalai",
    "name_ta": "சிறுமலை தலைமை மரவுரி ஆடைத் தொழிலாளர் மற்றும் நார்ப் பெருந்தச்சர்",
    "era": "Pandya Classical Era",
    "year_start": 700,
    "year_end": 800,
    "thinai": "kurinji",
    "summary_en": "The veteran hill craftsman of Sirumalai who mastered the selection of wild Antiaris and Ficus trees, engineered multi-grooved hardwood beaters, and produced golden, supple bark cloth supplied to Madurai monasteries.",
    "summary_ta": "சிறுமலை காடுகளில் மரப்பட்டைகளைத் தேர்ந்தெடுத்து, வரிப்பள்ளக் கட்டைகளால் தட்டி, மதுரை சமண-சைவ முனிவர்களுக்கான மரவுரி ஆடைகளைத் தயாரித்தளித்த தலைசிறந்த வனக் கலைஞர்.",
    "sources": [
      "Sirumalai Inscriptions",
      "Traditional Forest Crafts of Southern Tamil Nadu"
    ],
    "content": "---\nid: char-sirumalai-master-bark-cloth-beater-maravuri-thozhilan\ntitle: Master Bark-Cloth Beater & Forest Textile Specialist: Maravuri Thozhilan of Sirumalai\ntype: character\nera: Pandya Classical Era (c. 700 - 800 CE)\nthinai: kurinji (Highland Material Craft)\nstatus: canonical\n---\n\n# Master Bark-Cloth Beater & Forest Textile Specialist: Maravuri Thozhilan of Sirumalai\n\n## 1. Lineage in Forest Textiles\nLiving in the misty evergreen ridges of Sirumalai, the **Maravuri Thozhilan** preserved an ancient technology that linked Neolithic foraging knowledge with early historic religious life.\n\n## 2. Mastered Craftsmanship\n- Identifying trees with optimal phloem fiber density that could be peeled without killing the parent tree (*Ethir-tholi* harvesting).\n- Rhythmic hand-beating coordination that uniformly expanded narrow bast ribbons without tearing delicate fiber bridges.\n"
  },
  {
    "file": "knowledge/characters/char-alagar-malai-forest-fiber-gatherer-naar-kothon.md",
    "slug": "char-alagar-malai-forest-fiber-gatherer-naar-kothon",
    "category": "character",
    "name_en": "Sacred Hill Bast-Fiber Gatherer: Naar Kothon of Alagar Malai",
    "name_ta": "அழகர்மலை காடுறை நார்ப்பொருள் சேகரிப்பாளர்: நார் கொத்தோன்",
    "era": "Early Historic Era",
    "year_start": -200,
    "year_end": 50,
    "thinai": "kurinji",
    "summary_en": "The indigenous forest gatherer and fiber harvester of Alagar Malai who collected wild bast strips, retted fiber bundles in mountain springs, and supplied raw materials to ascetic monasteries in the cavern complex.",
    "summary_ta": "அழகர்மலை அடர்ந்த காடுகளில் மருத்துவ மரங்களின் நார்ப்பட்டைகளைச் சேகரித்து, சுனை நீரில் ஊறவைத்து, குகை முனிவர்களின் பாய்களுக்காக நார்ப்பொருட்களை வழங்கிய காட்டுவாழ் கலைஞர்.",
    "sources": [
      "Alagarmalai Tamil-Brahmi Epigraphs",
      "Sangam Kurinji Anthropological Notes"
    ],
    "content": "---\nid: char-alagar-malai-forest-fiber-gatherer-naar-kothon\ntitle: Sacred Hill Bast-Fiber Gatherer: Naar Kothon of Alagar Malai\ntype: character\nera: Early Historic Era (c. 200 BCE - 50 CE)\nthinai: kurinji (Forest Ethnobotany)\nstatus: canonical\n---\n\n# Sacred Hill Bast-Fiber Gatherer: Naar Kothon of Alagar Malai\n\n## 1. Ethnobotanical Knowledge\nStationed in the sacred forested valleys of Alagar Malai, the **Naar Kothon** possessed vast experiential knowledge of seasonal sap flow and bark peeling windows.\n\n## 2. Supply to Monastic Havens\nWorking alongside merchant benefactors, he ensured that the ascetic Jaina monks inhabiting the rock-shelters received clean, pliable bast mats and insect-resistant cordage for their daily contemplation retreats.\n"
  },
  {
    "file": "knowledge/places/place-sirumalai-ancient-bast-fiber-and-bark-haven.md",
    "slug": "place-sirumalai-ancient-bast-fiber-and-bark-haven",
    "category": "place",
    "name_en": "Sirumalai: Ancient Bast-Fiber Biosphere & Forest Textile Haven",
    "name_ta": "சிறுமலை - பண்டைய மர நார்ப்பொருள் காப்பகம் மற்றும் மரவுரித் தளம்",
    "era": "Sangam Classical Era",
    "year_start": -300,
    "year_end": 1000,
    "thinai": "kurinji",
    "summary_en": "Picturesque isolated mountain massif south of the Kodaganar river in Dindigul district celebrated in Silappadikaram for lush botanical biodiversity, medicinal springs, and continuous indigenous manufacture of beaten bark cloth and forest bast cordage.",
    "summary_ta": "திண்டுக்கல் மாவட்டத்தில் அமைந்துள்ள வளமான மலைத்தொடர்; சிலப்பதிகாரத்தில் போற்றப்பட்ட மூலிகைக் காடுகள், சுனைநீர் ஊற்றுகள் மற்றும் ஆதி மரவுரி ஆடை உற்பத்திக்குரிய தளம்.",
    "sources": [
      "Silappadikaram: Kadukankadhai",
      "Dindigul Gazetteer",
      "ASI Reports on Sirumalai Foothill Sites"
    ],
    "content": "---\nid: place-sirumalai-ancient-bast-fiber-and-bark-haven\ntitle: Sirumalai: Ancient Bast-Fiber Biosphere & Forest Textile Haven\ntype: place\nera: Sangam Classical Era (c. 300 BCE - 1000 CE)\nthinai: kurinji (Highland Ethnobotany & Montane Geography)\nstatus: canonical\n---\n\n# Sirumalai: Ancient Bast-Fiber Biosphere & Forest Textile Haven\n\n## 1. Geography & Environmental Wealth\n**Sirumalai** (lat 10.2000° N, lng 77.9900° E) is an isolated mountainous plateau rising to 1,600 meters elevation in central-southern Tamil Nadu, situated between Dindigul and Madurai.\n\nFed by perennial mountain streams and dense moist-deciduous forest cover, it nurtured vast groves of fiber-producing trees (*Ficus*, *Antiaris*, *Sterculia*).\n\n## 2. Cultural & Literary Celebration\nIn *Silappadikaram*, Kovalan and Kannagi bypass the slopes of Sirumalai on their journey to Madurai, with the poet Ilango Adigal describing its aromatic slopes, wild plantain groves, and sacred ascetics' forest dwellings where beaten bark garments were manufactured and worn.\n"
  }
]
EDGES = [
  [
    "text-tirumurukarruppadai-hermit-bark-garments-maravuri-poetry",
    "celebrates_ascetic_vestments",
    "concept-ascetic-hermit-bark-vestments-and-proto-paper-writing-sheets-maravuri",
    "cultural",
    "Sangam Classical Era",
    "Tirumurukarruppadai describing sages draped in supple beaten bark garments",
    "Tirumurukarruppadai 126-135"
  ],
  [
    "insc-sirumalai-pandya-forest-fiber-tribute-charters",
    "records_bark_cloth_tribute_at",
    "place-sirumalai-ancient-bast-fiber-and-bark-haven",
    "epigraphical",
    "Pandya Classical Era",
    "Pandya inscriptions recording annual levies of beaten maravuri sheets",
    "SII Vol. XIV"
  ],
  [
    "insc-alagar-malai-jaina-cavern-bark-mat-endowment-epigraphs",
    "records_bark_mat_donations_for",
    "concept-ascetic-hermit-bark-vestments-and-proto-paper-writing-sheets-maravuri",
    "epigraphical",
    "Early Historic Era",
    "Tamil-Brahmi inscriptions endowing bast fiber mats for cavern ascetics",
    "Mahadevan 2003"
  ],
  [
    "concept-ficus-and-antiaris-inner-bast-peeling-and-retting-mechanics",
    "supplies_retted_bast_for",
    "concept-grooved-hardwood-mallet-tapa-beating-and-fiber-felting-thattu-thadi",
    "technological",
    "Early Historic Era",
    "Harvested and retted secondary phloem strips ready for anvil mallet beating",
    "Cardon 2007"
  ],
  [
    "concept-grooved-hardwood-mallet-tapa-beating-and-fiber-felting-thattu-thadi",
    "produces_supple_sheets_for",
    "concept-botanical-starch-sizing-and-herbal-mastic-pasai-finishing",
    "mechanical",
    "Early Historic Era",
    "Beaten felted bark sheets saturated with rice starch and neem preservatives",
    "Kennedy 1993"
  ],
  [
    "concept-botanical-starch-sizing-and-herbal-mastic-pasai-finishing",
    "creates_smooth_surfaces_for",
    "concept-ascetic-hermit-bark-vestments-and-proto-paper-writing-sheets-maravuri",
    "chemical",
    "Early Historic Era",
    "Starch-sized bark sheets converted into writing surfaces and hermit robes",
    "Sarma 1985"
  ],
  [
    "char-sirumalai-master-bark-cloth-beater-maravuri-thozhilan",
    "beat_bark_cloth_at",
    "place-sirumalai-ancient-bast-fiber-and-bark-haven",
    "social",
    "Pandya Classical Era",
    "Master highland artisan specialized in tapa-style bark peeling and felting",
    "Sirumalai Crafts"
  ],
  [
    "char-alagar-malai-forest-fiber-gatherer-naar-kothon",
    "harvested_bast_fibers_for",
    "concept-ficus-and-antiaris-inner-bast-peeling-and-retting-mechanics",
    "technological",
    "Early Historic Era",
    "Forester selecting mature Antiaris trees and retting fibers in mountain springs",
    "Alagarmalai"
  ],
  [
    "char-sirumalai-master-bark-cloth-beater-maravuri-thozhilan",
    "utilized_grooved_mallets",
    "concept-grooved-hardwood-mallet-tapa-beating-and-fiber-felting-thattu-thadi",
    "technological",
    "Pandya Classical Era",
    "Operating four-sided grooved ironwood beaters to expand bast into sheets",
    "Traditional Crafts"
  ],
  [
    "concept-ascetic-hermit-bark-vestments-and-proto-paper-writing-sheets-maravuri",
    "harvested_from_forests_of",
    "place-sirumalai-ancient-bast-fiber-and-bark-haven",
    "environmental",
    "Sangam Classical Era",
    "Highland biosphere supplying supple inner bark textiles for Tamil ascetics",
    "Silappadikaram"
  ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 22 Corpus 3: Beaten Bark-Cloth Manufacture & Sizing into Moolam Chronicles & Life Graph...")

    # Phase 1: Write Markdown Files
    print("\n[Phase 1] Writing 10 Markdown Knowledge Dossiers...")
    for d in DOSSIERS:
        full_path = os.path.join(MOOLAM_KNOWLEDGE, d["file"])
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"  ✓ Wrote: {d['file']}")

    # Phase 2: PostgreSQL Lore Nodes Upsert
    print(f"\n[Phase 2] Connecting to PostgreSQL at {DB_URL}...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    nodes_upserted = 0
    for d in DOSSIERS:
        slug = d["slug"]
        props = json.dumps({"category": d["category"], "canonical_file": d["file"]})
        cur.execute("""
            INSERT INTO lore_nodes (
                id, slug, node_type, name_en, name_ta, era, year_start, year_end,
                thinai, summary_en, summary_ta, sources, layer, properties, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, NOW()
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
                sources = EXCLUDED.sources,
                layer = EXCLUDED.layer,
                properties = EXCLUDED.properties,
                created_at = NOW();
        """, (
            str(uuid.uuid4()),
            slug,
            d["category"],
            d["name_en"],
            d["name_ta"],
            d["era"],
            d["year_start"],
            d["year_end"],
            d["thinai"],
            d["summary_en"],
            d["summary_ta"],
            d["sources"],
            "historical_proof",
            props
        ))
        nodes_upserted += 1
        print(f"  ✓ Upserted node: {slug}")

    conn.commit()
    print(f"Phase 2 complete: {nodes_upserted} lore nodes upserted.")

    # Phase 3: Relational Cross-Domain Edges
    print(f"\n[Phase 3] Inserting {len(EDGES)} Relational Cross-Domain Edges...")
    edges_inserted = 0
    for edge in EDGES:
        src, rel, tgt, layer, era, desc, evidence = edge
        cur.execute("""
            DELETE FROM lore_edges 
            WHERE source_slug = %s AND target_slug = %s AND relation_type = %s;
        """, (src, tgt, rel))

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
    print(f"Phase 3 complete: {edges_inserted} edges processed.")

    # Phase 4: Vector Embeddings
    print("\n[Phase 4] Generating 1024-dim BGE-M3 Embeddings via Ollama...")
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
                f"shelf-{d['category']}s",
                ch["language"],
                ch["title"],
                ch["content"],
                d["file"],
                emb_str
            ))
            total_chunks += 1
        print(f"  ✓ Embedded 2 chunks for: {slug}")

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n🎉 Batch 22 Corpus 3: Beaten Bark-Cloth Manufacture & Sizing Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
