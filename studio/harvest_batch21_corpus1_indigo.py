#!/usr/bin/env python3
# Ingestion harvester for Batch 21 Corpus 1: Indigo Dyeing & Calico Printing
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
    "file": "knowledge/texts/text-perumpanarruppadai-indigo-dyeing-and-blue-cloth-poetry.md",
    "slug": "text-perumpanarruppadai-indigo-dyeing-and-blue-cloth-poetry",
    "category": "text",
    "name_en": "Perumpanarruppadai Sangam Verses on Indigo Vat Dyeing & Deep Azure Textiles",
    "name_ta": "பெரும்பாணாற்றுப்படை நீலச் சாயத் தொழிற்பட்டறை மற்றும் நீல ஆடைப் பாடல்கள்",
    "era": "Sangam Classical Era",
    "year_start": -200,
    "year_end": 100,
    "thinai": "marutham",
    "summary_en": "Sangam poetry in Perumpanarruppadai and Akananuru documenting ancient Tamil indigo vat dyeing: fermenting green Neeli leaves, reducing the dyebath with alkaline wood-ash lye, and dipping bleached cotton fabrics to produce indelible dark blue (Karun-Niram) and peacock-feather cerulean cloths.",
    "summary_ta": "அவுரி (நீலி) இலைகளை நொதிக்க வைத்து, உவர்ச்சாம்பல் நீர் சேர்த்து, வெளுத்த பருத்தி ஆடைகளைத் தோய்த்து நீல நிறம் மற்றும் மயில் கழுத்து வண்ண ஆடைகளை உருவாக்கிய பண்டைய தமிழர் சாயத் தொழில்நுட்பத்தைப் போற்றும் சங்கப் பாடல்கள்.",
    "sources": [
      "Perumpanarruppadai 220-235",
      "Akananuru 387",
      "Mahalingam: South Indian Polity & Guild Crafts"
    ],
    "content": "---\nid: text-perumpanarruppadai-indigo-dyeing-and-blue-cloth-poetry\ntitle: Perumpanarruppadai Sangam Verses on Indigo Vat Dyeing & Deep Azure Textiles\ntype: text\nera: Sangam Classical Era (c. 200 BCE - 100 CE)\nthinai: marutham (Textile Agronomy & Urban Guilds)\nstatus: canonical\n---\n\n# Perumpanarruppadai Sangam Verses on Indigo Vat Dyeing & Deep Azure Textiles\n\n## 1. Classical Descriptions of Indigo Craft\nIn Sangam literature, the natural blue dye extracted from the plant **Neeli (அவுரி / *Indigofera tinctoria*)** was famed across the ancient world. The deep azure and midnight-blue fabrics produced in Tamil riverine centers were prized from Rome to Alexandria as *Indicum*.\n\nIn *Perumpanarruppadai*, the poet describes the vibrant industrial quarters of weavers and dyers:\n> \"நீலக் கச்சைப் பூவாடை நுண்துகில்...\n> ஆவியன்ன அவிர்நூற் கலிங்கம்...\"\n*(Fine woven cotton robes resembling condensed steam, dyed with rich floral borders and deep indigo sashes).*\n\n*Akananuru* 387 explicitly references the fermentation vats situated near running streams, where Neeli leaves were steeped until the water turned dark green-blue with pungent effervescence.\n\n## 2. Technical Insights Preserved in Poetry\n1. **Neeli-Katchu**: Indigo-dyed textile girdles worn by warriors and noblemen.\n2. **Mayil-Kazhuthu (Peacock-Neck Blue)**: Layered dipping of yellow turmeric-dyed cloth into light indigo baths to produce iridescent teal and peacock-neck shades.\n3. **Mani-Niram**: Saturated deep navy blues achieved through multiple successive dips and aerobic oxidation exposures.\n"
  },
  {
    "file": "knowledge/inscriptions/insc-karur-chera-textile-dyers-guild-epigraphs.md",
    "slug": "insc-karur-chera-textile-dyers-guild-epigraphs",
    "category": "inscription",
    "name_en": "Karur Chera Textile Dyers Guild & Vat Tax Charters",
    "name_ta": "கரூர் சேரர் சாயத் தொழிலாளர் கில்டு மற்றும் சாயத்தொட்டி வரிப் பட்டயங்கள்",
    "era": "Sangam Classical Era",
    "year_start": -150,
    "year_end": 150,
    "thinai": "marutham",
    "summary_en": "Tamil-Brahmi inscribed potsherds and Chera lead-bronze coin legends from the Amaravathi riverbed at Karur attesting to organized textile dyers guilds (Vannar / Sayanakarar), commercial dye-vats (Thotti), and international textile trade.",
    "summary_ta": "கரூர் அமராவதி ஆற்றுப் படுகையில் கண்டறியப்பட்ட தமிழ்-பிராமி பொறித்த பானை ஓடுகள் மற்றும் சேரர் நாணயங்கள்; அவுரிச் சாயத் தொட்டிகள் மற்றும் நெசவாளர் வணிகக் குழுக்கள் குறித்த தொல்லியல் சான்றுகள்.",
    "sources": [
      "Nagapattinam & Karur Excavation Reports (ASI/TNSDA)",
      "Krishnamurthy: Coins of the Cheras in Karur"
    ],
    "content": "---\nid: insc-karur-chera-textile-dyers-guild-epigraphs\ntitle: Karur Chera Textile Dyers Guild & Vat Tax Charters\ntype: inscription\nera: Sangam Classical Era (c. 150 BCE - 150 CE)\nthinai: marutham (Commercial Epigraphy & Guild Organization)\nstatus: canonical\n---\n\n# Karur Chera Textile Dyers Guild & Vat Tax Charters\n\n## 1. Epigraphical Provenance: Karur (Vanji)\nKarur, the inland capital of the Early Cheras on the Amaravathi river, was a colossal metallurgical, numismatic, and textile manufacturing emporium. \n\nExcavations have unearthed multiple Tamil-Brahmi graffiti on Black-and-Red Ware shards reading:\n- **Atan Vannan (ஆதன் வண்ணன்)**: \"Vannan\" indicating a professional master dyer/bleacher.\n- **Thotti-Kani (தொட்டிக் காணி)**: Epigraphical records of industrial brick-lined cisterns used for multi-stage cloth washing and dye fermentation.\n\n## 2. Trade Integration\nThe Chera state actively taxed dye-vats (*Thotti-Irai*) while granting customs exemptions on indigo cakes transported by pack-bullocks through the Palakkad Gap toward the port of Muziris for shipment to Egypt and the Mediterranean.\n"
  },
  {
    "file": "knowledge/inscriptions/insc-uraiyur-early-chola-indigo-vat-charters.md",
    "slug": "insc-uraiyur-early-chola-indigo-vat-charters",
    "category": "inscription",
    "name_en": "Uraiyur Early Chola Industrial Indigo Dye-Vat Excavation Charters",
    "name_ta": "உறையூர் முற்காலச் சோழர் அவுரிச் சாயத் தொட்டி அகழாய்வுப் பதிவுகள்",
    "era": "Early Historic Era",
    "year_start": -200,
    "year_end": 200,
    "thinai": "marutham",
    "summary_en": "Excavation records from the Archaeological Survey of India and Madras University at Uraiyur uncovering interconnected burnt-brick dye vats with plastered drains, settling tanks, and carbonized indigo pigment residues from early historic Chola levels.",
    "summary_ta": "திருச்சிராப்பள்ளி உறையூரில் அகழப்பட்ட பண்டைய சோழர் காலத்து சுடுசெங்கல் சாயத் தொட்டிகள், வடிகால் வாய்க்கால்கள் மற்றும் படிந்த அவுரிச் சாயக் கசடுகள் குறித்த இந்தியத் தொல்லியல் துறை அகழாய்வுப் பதிவுகள்.",
    "sources": [
      "ASI Excavation Memoir: Uraiyur 1965-1969",
      "Rajan: Early Historic Brick Architecture of the Kaveri Delta"
    ],
    "content": "---\nid: insc-uraiyur-early-chola-indigo-vat-charters\ntitle: Uraiyur Early Chola Industrial Indigo Dye-Vat Excavation Charters\ntype: inscription\nera: Early Historic Era (c. 200 BCE - 200 CE)\nthinai: marutham (Urban Industrial Archaeology)\nstatus: canonical\n---\n\n# Uraiyur Early Chola Industrial Indigo Dye-Vat Excavation Charters\n\n## 1. Archaeological Discovery at Uraiyur\nExcavations at Uraiyur (the historic inland capital of the Sangam Cholas) conducted by the University of Madras exposed two rectangular structures constructed of fine burnt bricks ($45 \\times 28 \\times 7\\text{ cm}$), complete with lime-surkhi plastering:\n- **Dimensions**: Cisterns measuring $1.8 \\times 1.2\\text{ meters}$, with depths of $0.9\\text{ meters}$.\n- **Conduit Drainage**: Clay pipe conduits connected the upper steeping vat to a lower settling tank to permit gradual liquid decantation.\n\n## 2. Chemical Analysis of Sediments\nChemical analysis of soil sediments from the floor of the cisterns revealed significant traces of indigo dye derivatives (indigotin and indirubin) embedded in calcium carbonate matrices, confirming the structures functioned as industrial **dyeing vats** for export cottons.\n"
  },
  {
    "file": "knowledge/concepts/concept-indigofera-tinctoria-leaf-fermentation-and-hydrolysis-neeli.md",
    "slug": "concept-indigofera-tinctoria-leaf-fermentation-and-hydrolysis-neeli",
    "category": "concept",
    "name_en": "Indigofera Tinctoria Leaf Fermentation, Enzymatic Hydrolysis & Indican Cleavage (Neeli)",
    "name_ta": "அவுரி இலை நொதித்தல், என்சைம் நீராற்பகுப்பு மற்றும் இண்டிகான் பிரித்தெடுப்பு நுட்பம்",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 400,
    "thinai": "marutham",
    "summary_en": "The bio-chemical process of ancient Tamil indigo extraction: harvesting fresh Neeli leaves before flowering, steeping in water tanks at 30-35°C to induce microbial fermentation, enzymatically hydrolyzing the glycoside indican into indoxyl and glucose, followed by vigorous aeration.",
    "summary_ta": "பூ பூக்கும் முன் அறுவடை செய்யப்பட்ட அவுரித் தழைகளை வெதுவெதுப்பான நீரில் ஊறவைத்து, நுண்ணுயிரி நொதித்தல் மூலம் இண்டிகான் கிளைக்கோசைடை உடைத்து இண்டாக்சிலாக மாற்றி காற்றில் ஆக்சிஜனேற்றம் செய்யும் பண்டைய உயிரி-வேதியியல் நுட்பம்.",
    "sources": [
      "Balfour: The Cyclopaedia of India (Indigo)",
      "Cardon: Natural Dyes: Sources, Tradition, Technology",
      "Indian Journal of History of Science (Ancient Dyes)"
    ],
    "content": "---\nid: concept-indigofera-tinctoria-leaf-fermentation-and-hydrolysis-neeli\ntitle: Indigofera Tinctoria Leaf Fermentation, Enzymatic Hydrolysis & Indican Cleavage (Neeli)\ntype: concept\nera: Early Historic Era (c. 400 BCE - 400 CE)\nthinai: marutham (Bio-Chemical Industrial Pyrotechnics)\nstatus: canonical\n---\n\n# Indigofera Tinctoria Leaf Fermentation, Enzymatic Hydrolysis & Indican Cleavage (Neeli)\n\n## 1. Botanical Source: Neeli (அவுரி)\nThe plant *Indigofera tinctoria* (family Fabaceae) was cultivated extensively in the fertile clay loams of the Kaveri, Amaravathi, and Vaigai river floodplains. \n\nThe active color precursor in the green leaf is **indican** (indoxyl-$\\beta$-D-glucoside), a colorless, water-soluble glucoside.\n\n## 2. Biochemical Fermentation Kinetics\n1. **Harvesting & Steeping**: Fresh leaves harvested at dawn were packed tightly under bamboo latticework inside brick cisterns filled with water.\n2. **Microbial Hydrolysis**: Over 10 to 14 hours at ambient temperatures (30–35°C), naturally occurring plant enzymes ($\\beta$-glucosidase) and bacteria fermented the mixture:\n   $$\\text{Indican} + \\text{H}_2\\text{O} \\xrightarrow{\\beta\\text{-glucosidase}} \\text{Indoxyl} + \\text{Glucose}$$\n3. **Liquid Decantation**: As the liquor turned a golden yellowish-green, it was drained into adjacent beating vats (*Medu-thotti*).\n"
  },
  {
    "file": "knowledge/concepts/concept-alkaline-ash-and-slaked-lime-vat-reduction-chemistry.md",
    "slug": "concept-alkaline-ash-and-slaked-lime-vat-reduction-chemistry",
    "category": "concept",
    "name_en": "Alkaline Wood-Ash Lye, Slaked Lime Reduction & Leuco-Indigo Solubilization",
    "name_ta": "சாம்பல் கார நீர், நீற்றுச்சுண்ணாம்பு ஒடுக்க வினை மற்றும் கரையக்கூடிய வெண்-நீலி உருவாக்கம்",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 400,
    "thinai": "marutham",
    "summary_en": "The reduction chemistry of ancient indigo vat dyeing: insoluble blue indigotin must be chemically reduced to water-soluble leuco-indigo (white indigo) to penetrate cellulose fibers. Ancient Tamil artisans accomplished this by adding wood-ash lye (potassium carbonate), slaked lime, and fermented toddy.",
    "summary_ta": "நீரில் கரையாத நீல வண்ண இண்டிகோவை செலுலோஸ் இழைகளில் ஊடுருவச் செய்ய, உவர்ச்சாம்பல் கார நீர், நீற்றுச்சுண்ணாம்பு மற்றும் புளித்த கள் சேர்த்து கரையக்கூடிய வெண்-நீலியாக மாற்றும் பண்டைய கார-ஒடுக்க வேதியியல் நுட்பம்.",
    "sources": [
      "Clark: The Chemistry of Natural Dyes",
      "Sethi: Traditional Textile Chemistry of India",
      "Archaeometry Journal: Ancient Vat Dyes"
    ],
    "content": "---\nid: concept-alkaline-ash-and-slaked-lime-vat-reduction-chemistry\ntitle: Alkaline Wood-Ash Lye, Slaked Lime Reduction & Leuco-Indigo Solubilization\ntype: concept\nera: Early Historic Era (c. 400 BCE - 400 CE)\nthinai: marutham (Textile Reduction Chemistry)\nstatus: canonical\n---\n\n# Alkaline Wood-Ash Lye, Slaked Lime Reduction & Leuco-Indigo Solubilization\n\n## 1. The Solubilization Paradox of Indigo\nUnlike water-soluble mordant dyes, indigo pigment (**indigotin**, $\\text{C}_{16}\\text{H}_{10}\\text{N}_2\\text{O}_2$) is entirely insoluble in water, weak acids, or alcohol. It cannot bind to cotton cellulose fibers in its oxidized blue state.\n\nTo dye cloth, it must undergo **chemical reduction** to its enolic form: **leuco-indigo** (white indigo, $\\text{C}_{16}\\text{H}_{12}\\text{N}_2\\text{O}_2$), which is soluble only in strongly alkaline solutions ($\\text{pH} \\approx 10.5 - 12.0$).\n\n## 2. Ancient Reagent Formulation\nWithout synthetic reducing agents, ancient Tamil dyers established an organic anaerobic fermentation vat:\n1. **Alkaline Flux**: Leached wood-ash lye (*Sambal-neer* / $\\text{K}_2\\text{CO}_3$) combined with slaked lime (*Neetru-chunnambu* / $\\text{Ca(OH)}_2$) to raise the bath pH.\n2. **Reducing Agents**: Fermenting organic sugars derived from palm toddy (*Kallu*), crushed overripe bananas, or tamarind seed pulp.\n3. **Anaerobic Microbes**: Bacteria metabolized the sugars, consuming dissolved oxygen and releasing hydrogen ions that reduced indigotin to soluble leuco-indigo.\n"
  },
  {
    "file": "knowledge/concepts/concept-leuco-indigo-aerobic-oxidation-and-cotton-fiber-binding.md",
    "slug": "concept-leuco-indigo-aerobic-oxidation-and-cotton-fiber-binding",
    "category": "concept",
    "name_en": "Leuco-Indigo Aerobic Atmospheric Oxidation & Inter-Polymer Cotton Binding Mechanics",
    "name_ta": "வெண்-நீலி வளிமண்டல ஆக்சிஜனேற்றம் மற்றும் பருத்தி இழைப் பிணைப்பு இயற்பியல்",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 400,
    "thinai": "marutham",
    "summary_en": "The physical-chemical bonding of indigo onto cotton: leuco-indigo molecules diffuse into the amorphous regions of cellulose microfibrils while submerged. Upon removal and air exposure, atmospheric oxygen re-oxidizes the soluble compound into insoluble microcrystalline indigotin, locking it permanently inside the fiber.",
    "summary_ta": "பருத்தி இழைகளின் நுண்ணிய துளைகளுக்குள் ஊடுருவிய வெண்-நீலிக் கரைசல், காற்றில் வெளியே எடுத்து உலர்த்தும்போது ஆக்சிஜனுடன் வினைபுரிந்து மீண்டும் கரையாத நீல இண்டிகோ படிகங்களாக மாறி இழைகளுக்குள் நிரந்தரமாகப் பூட்டிக்கொள்ளும் இயற்பியல் நுட்பம்.",
    "sources": [
      "Cardon: Natural Dyes",
      "Peters: Textile Chemistry",
      "Grewal: Indigo in Ancient Trade"
    ],
    "content": "---\nid: concept-leuco-indigo-aerobic-oxidation-and-cotton-fiber-binding\ntitle: Leuco-Indigo Aerobic Atmospheric Oxidation & Inter-Polymer Cotton Binding Mechanics\ntype: concept\nera: Early Historic Era (c. 400 BCE - 400 CE)\nthinai: marutham (Polymer Physics & Atmospheric Oxidation)\nstatus: canonical\n---\n\n# Leuco-Indigo Aerobic Atmospheric Oxidation & Inter-Polymer Cotton Binding Mechanics\n\n## 1. Submersion and Diffusion\nWhen wet spun cotton yarn or woven cloth is lowered into the reduced, lime-yellow vat liquor, the planar leuco-indigo molecules diffuse through the porous cellulose matrix of the cotton fibers.\n\nBecause leuco-indigo possesses affinity for cellulose via hydrogen bonding and van der Waals interactions, it distributes evenly throughout the interior amorphous regions of the fiber.\n\n## 2. Atmospheric Aerial Oxidation (The Miracle of Color Emergence)\nUpon pulling the fabric from the vat, it emerges a pale translucent yellow-green. As it is shaken and exposed to ambient air:\n$$\\text{Leuco-Indigo (soluble)} + \\text{O}_2 \\rightarrow \\text{Indigotin (insoluble blue)} + \\text{H}_2\\text{O}$$\n\nWithin 3 to 5 minutes, the fabric dramatically transitions through turquoise, sky blue, and finally into deep royal navy blue. \n\n## 3. Physical Entrapment\nBecause the re-oxidized indigotin forms insoluble crystalline clusters larger than the inter-chain pore spaces of the cellulose fibrils, it cannot be washed out by water or mechanical agitation, bestowing ancient Tamil cottons with unmatched wash-fastness.\n"
  },
  {
    "file": "knowledge/concepts/concept-mud-resist-wax-and-alum-mordant-calico-printing-kalamkari.md",
    "slug": "concept-mud-resist-wax-and-alum-mordant-calico-printing-kalamkari",
    "category": "concept",
    "name_en": "Mud-Resist, Molten Beeswax Printing & Alum Mordant Calico Patterning (Kalamkari)",
    "name_ta": "களிமண்-மெழுகு எதிர்ப்பு அச்சு, படிகாரப் பற்றூன்றி மற்றும் சித்திர ஆடை நுட்பம்",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": 500,
    "thinai": "marutham",
    "summary_en": "The resist-dyeing and mordant-printing technologies of early Tamil calico textiles: applying river clay mixed with gum arabic or molten beeswax via carved wooden blocks (Achchu) or bamboo reed pens (Kalam), preventing indigo penetration to create white reserve lines, and cross-dyeing with madder and alum.",
    "summary_ta": "செதுக்கப்பட்ட மர அச்சுகள் அல்லது மூங்கில் தூரிகை கொண்டு களிமண் மற்றும் தேன்மெழுகை ஆடைகள் மீது வரைந்து, அவுரிச் சாயத்தில் தோய்த்து, மெழுகு நீக்கி வெள்ளை வடிவங்கள் மற்றும் படிகாரத்தின் மூலம் சிவப்பு-நீல சித்திர ஆடைகளை உருவாக்கிய பண்டைய நுட்பம்.",
    "sources": [
      "Varadarajan: South Indian Traditions of Kalamkari",
      "Irwin: Indian Painted and Printed Fabrics",
      "Gittinger: Master Dyeworks of India"
    ],
    "content": "---\nid: concept-mud-resist-wax-and-alum-mordant-calico-printing-kalamkari\ntitle: Mud-Resist, Molten Beeswax Printing & Alum Mordant Calico Patterning (Kalamkari)\ntype: concept\nera: Early Historic Era (c. 300 BCE - 500 CE)\nthinai: marutham (Resist Chemistry & Block Printing)\nstatus: canonical\n---\n\n# Mud-Resist, Molten Beeswax Printing & Alum Mordant Calico Patterning (Kalamkari)\n\n## 1. Resist-Dyeing Principles\nTo produce patterned calico fabrics with crisp multi-color designs, ancient Tamil artisans utilized **resist media** that physically prevented indigo from penetrating designated areas of the cloth.\n\n### The Two Primary Resist Formulations:\n1. **Dhabu Mud-Resist (*Man-Echirikkai*)**: A thick paste of fine alluvial clay, gum karaya, slaked lime, and fermented wheat/rice flour, stamped onto the cloth using carved hardwood blocks (*Achchu*).\n2. **Molten Beeswax (*Thaen-Mezhugu*)**: Applied using a copper-reservoir reed pen (*Kalam*), creating fine fluid lines for royal figurations and temple banners.\n\n## 2. Multi-Bath Polychromy\n1. **First Resist & Indigo Dip**: Fabric stamped with mud-resist is dipped in the indigo vat, producing deep blue fields with reserved white motifs.\n2. **Resist Removal**: The cloth is washed in boiling river water to soften and wash away the mud and wax.\n3. **Alum Mordanting**: For red areas, the artisan hand-paints an alum (*Padi-karam* / potassium aluminium sulfate) solution onto targeted zones and dips the cloth in a boiling madder (*Manjistha*) bath. The alum acts as a coordination cross-linker between the alizarin dye and the cellulose chain.\n"
  },
  {
    "file": "knowledge/characters/char-karur-master-indigo-vat-dyer-neeli-vannan.md",
    "slug": "char-karur-master-indigo-vat-dyer-neeli-vannan",
    "category": "character",
    "name_en": "Master Indigo Vat Dyer & Guild Alderman: Neeli Vannan of Karur",
    "name_ta": "கரூர் தலைமை அவுரிச் சாயத் தொழிலாளர் மற்றும் கில்டு தலைவர்: நீலி வண்ணன்",
    "era": "Sangam Classical Era",
    "year_start": -100,
    "year_end": 50,
    "thinai": "marutham",
    "summary_en": "Epitome of the skilled Chera textile dyers of Karur who directed industrial brick-lined fermentation vats, calibrated wood-ash alkaline levels, and produced export-quality azure and royal navy cottons traded across the Indian Ocean.",
    "summary_ta": "அமராவதி நதிக்கரைக் கரூரில் பிரம்மாண்டமான அவுரிச் சாயத் தொட்டிகளை இயக்கி, கார-அமில விகிதங்களைத் துல்லியமாகக் கட்டுப்படுத்தி, உரோம வணிகர்களுக்கு நீல ஆடைகளைத் தயாரித்தளித்த தலைசிறந்த சாயத் தொழில் வல்லுநர்.",
    "sources": [
      "Karur Excavation Reports",
      "Sangam Inscribed Pottery Coramandel Series"
    ],
    "content": "---\nid: char-karur-master-indigo-vat-dyer-neeli-vannan\ntitle: Master Indigo Vat Dyer & Guild Alderman: Neeli Vannan of Karur\ntype: character\nera: Sangam Classical Era (c. 100 BCE - 50 CE)\nthinai: marutham (Textile Industrial Craft)\nstatus: canonical\n---\n\n# Master Indigo Vat Dyer & Guild Alderman: Neeli Vannan of Karur\n\n## 1. Professional Status & Lineage\nOperating along the banks of the Amaravathi river in the Chera capital of Karur, the **Neeli Vannan** was an elite master chemical craftsman and alderman of the local textile dyers guild (*Sayanakara-Nigamam*).\n\n## 2. Chemical Mastery\n- **Vat Diagnosis by Scent and Sheen**: Experienced vat masters never used modern pH meters; they judged the health of the reduced vat by its characteristic coppery iridescent surface film (*Arakku-Aadai*) and sweet fermented aroma.\n- **Dipping Cadence**: Regulating the immersion time (exactly 10 to 15 minutes) and aeration intervals to achieve uniform shade reproducibility across hundreds of bolt lengths.\n"
  },
  {
    "file": "knowledge/characters/char-uraiyur-calico-block-printer-achchu-thozhilan.md",
    "slug": "char-uraiyur-calico-block-printer-achchu-thozhilan",
    "category": "character",
    "name_en": "Master Calico Block Carver & Resist Printer: Achchu Thozhilan of Uraiyur",
    "name_ta": "உறையூர் மர அச்சுச் செதுக்குநர் மற்றும் துணி அச்சுப் பதிப்பாளர்",
    "era": "Early Historic Era",
    "year_start": -150,
    "year_end": 50,
    "thinai": "marutham",
    "summary_en": "The veteran Chola wood-carver and textile artist of Uraiyur who engraved fine teakwood relief printing blocks with floral, avian, and geometric patterns for mud-resist calico printing on handloom cottons.",
    "summary_ta": "உறையூர் சோழர் பட்டறைகளில் தேக்கு மரத்தில் நுட்பமான பூ வேலைப்பாடுகள் கொண்ட அச்சுக்கட்டைகளைச் செதுக்கி, களிமண்-மெழுகு பூச்சுகளால் வண்ணச் சித்திர ஆடைகளை அச்சிட்ட முதன்மை மரக் கலைஞர்.",
    "sources": [
      "Uraiyur Excavations (University of Madras)",
      "Varadarajan: South Indian Textile Crafts"
    ],
    "content": "---\nid: char-uraiyur-calico-block-printer-achchu-thozhilan\ntitle: Master Calico Block Carver & Resist Printer: Achchu Thozhilan of Uraiyur\ntype: character\nera: Early Historic Era (c. 150 BCE - 50 CE)\nthinai: marutham (Block Printing & Wood Carving)\nstatus: canonical\n---\n\n# Master Calico Block Carver & Resist Printer: Achchu Thozhilan of Uraiyur\n\n## 1. Craft Lineage\nSituated in the weaver quarters of Uraiyur flanking the Kaveri river, the **Achchu Thozhilan** combined the skills of a master relief wood-carver with deep understanding of textile pigment chemistry.\n\n## 2. Printing Block Engineering\n- **Timber Selection**: Carving seasoned *Ilupai* or teakwood blocks (*Mara-Achchu*) with relief patterns up to 15 mm deep to hold viscous resist mud without clogging.\n- **Air Release Channels**: Drilling tiny relief pin-holes through the block body to allow air to escape when the block was pressed hard onto the fabric spread across padded printing tables.\n- **Alignment Registration**: Incorporating brass corner pins that permitted flawless alignment (*Poruthu*) across repetitive textile patterns.\n"
  },
  {
    "file": "knowledge/places/place-karur-ancient-indigo-and-textile-haven.md",
    "slug": "place-karur-ancient-indigo-and-textile-haven",
    "category": "place",
    "name_en": "Karur: Ancient Indigo Industrial Haven & Chera Textile Emporium",
    "name_ta": "கரூர் - பண்டைய அவுரிச் சாயத் தொழிற்பட்டினம் மற்றும் சேரர் ஆடைப் பெருநகர்",
    "era": "Sangam Classical Era",
    "year_start": -300,
    "year_end": 300,
    "thinai": "marutham",
    "summary_en": "Historic inland capital of the Early Cheras on the Amaravathi river in western Tamil Nadu, renowned as a colossal textile manufacturing, indigo vat dyeing, and international coin-minting emporium connecting peninsular cotton fields to global Roman trade.",
    "summary_ta": "மேற்கு தமிழகத்தில் அமராவதி நதிக்கரையில் அமைந்துள்ள பண்டைய சேரர் தலைநகர்; உலகப்புகழ் பெற்ற பருத்தி நெசவு, அவுரிச் சாயத் தொட்டிகள் மற்றும் உரோம வர்த்தக ஆடை ஏற்றுமதி மையம்.",
    "sources": [
      "Karur Excavations (TNSDA)",
      "Suresh: Roman Antiquities in Tamil Nadu",
      "Purananuru 373"
    ],
    "content": "---\nid: place-karur-ancient-indigo-and-textile-haven\ntitle: Karur: Ancient Indigo Industrial Haven & Chera Textile Emporium\ntype: place\nera: Sangam Classical Era (c. 300 BCE - 300 CE)\nthinai: marutham (Textile Geography & Trade Emporium)\nstatus: canonical\n---\n\n# Karur: Ancient Indigo Industrial Haven & Chera Textile Emporium\n\n## 1. Strategic Riverine Geography\n**Karur** (lat 10.9600° N, lng 78.0800° E), known in ancient texts as *Vanji-Muthur*, occupied a strategic nexus on the Amaravathi river, a major tributary of the Kaveri. \n\nIts position placed it at the junction of:\n- The rich black-cotton soils (*Karisal-man*) of the Kongu basin.\n- Direct river transportation linking the western Ghats to the Coromandel coast.\n- The trans-peninsular caravan highway through the Palakkad Gap leading directly to Muziris.\n\n## 2. Textile Archeological Record\nArchaeological surface collections and riverbed washings at Karur have yielded:\n- Thousands of terracotta spindle whorls and bone weaving needles.\n- Brick-lined dyeing cisterns along the riverbanks.\n- Roman amphorae sherds and gold aurei hoards confirming high-value Mediterranean textile exports.\n"
  }
]
EDGES = [
  [
    "text-perumpanarruppadai-indigo-dyeing-and-blue-cloth-poetry",
    "celebrates_indigo_fabrics",
    "concept-indigofera-tinctoria-leaf-fermentation-and-hydrolysis-neeli",
    "cultural",
    "Sangam Classical Era",
    "Perumpanarruppadai verses celebrating deep blue dyed cotton textiles",
    "Perumpanarruppadai 220-235"
  ],
  [
    "insc-karur-chera-textile-dyers-guild-epigraphs",
    "records_dyers_guild_at",
    "place-karur-ancient-indigo-and-textile-haven",
    "epigraphical",
    "Sangam Classical Era",
    "Tamil-Brahmi pot graffiti recording professional textile dyers",
    "Karur Excavations"
  ],
  [
    "insc-uraiyur-early-chola-indigo-vat-charters",
    "documents_excavated_vats_at",
    "concept-alkaline-ash-and-slaked-lime-vat-reduction-chemistry",
    "archaeological",
    "Early Historic Era",
    "Burnt-brick dyeing cisterns and indigo sediment analysis",
    "Uraiyur Memoir"
  ],
  [
    "concept-indigofera-tinctoria-leaf-fermentation-and-hydrolysis-neeli",
    "yields_crude_pigment_for",
    "concept-alkaline-ash-and-slaked-lime-vat-reduction-chemistry",
    "chemical",
    "Early Historic Era",
    "Enzymatic cleavage producing indoxyl for alkaline vat reduction",
    "Cardon 2007"
  ],
  [
    "concept-alkaline-ash-and-slaked-lime-vat-reduction-chemistry",
    "enables_fiber_penetration_in",
    "concept-leuco-indigo-aerobic-oxidation-and-cotton-fiber-binding",
    "chemical",
    "Early Historic Era",
    "Solubilizing indigotin into leuco-indigo for cellulose diffusion",
    "Textile Chemistry"
  ],
  [
    "concept-mud-resist-wax-and-alum-mordant-calico-printing-kalamkari",
    "patterned_with_indigo_in",
    "place-karur-ancient-indigo-and-textile-haven",
    "industrial",
    "Early Historic Era",
    "Carved block printing and resist dyeing practiced in Chera workshops",
    "Varadarajan"
  ],
  [
    "char-karur-master-indigo-vat-dyer-neeli-vannan",
    "operated_vats_at",
    "place-karur-ancient-indigo-and-textile-haven",
    "social",
    "Sangam Classical Era",
    "Master dyer directing industrial fermentation vats on the Amaravathi",
    "Karur Epigraphs"
  ],
  [
    "char-uraiyur-calico-block-printer-achchu-thozhilan",
    "carved_printing_blocks_for",
    "concept-mud-resist-wax-and-alum-mordant-calico-printing-kalamkari",
    "artistic",
    "Early Historic Era",
    "Master wood carver producing relief blocks for calico printing",
    "Uraiyur Crafts"
  ],
  [
    "char-karur-master-indigo-vat-dyer-neeli-vannan",
    "mastered_vat_chemistry",
    "concept-alkaline-ash-and-slaked-lime-vat-reduction-chemistry",
    "technological",
    "Sangam Classical Era",
    "Expert calibration of wood-ash lye and microbial reduction",
    "Sayanakara Guild"
  ],
  [
    "concept-leuco-indigo-aerobic-oxidation-and-cotton-fiber-binding",
    "praised_in_sangam_verse",
    "text-perumpanarruppadai-indigo-dyeing-and-blue-cloth-poetry",
    "cultural",
    "Sangam Classical Era",
    "Vivid descriptions of azure dyed cloths resembling vapor",
    "Akananuru 387"
  ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 21 Corpus 1: Indigo Dyeing & Calico Printing into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 21 Corpus 1: Indigo Dyeing & Calico Printing Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
