#!/usr/bin/env python3
# Ingestion harvester for Batch 22 Corpus 1: Crucible Steel Pyrotechnics & Tuyeres
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
    "file": "knowledge/texts/text-perumpanarruppadai-iron-furnaces-and-crucible-poetry.md",
    "slug": "text-perumpanarruppadai-iron-furnaces-and-crucible-poetry",
    "category": "text",
    "name_en": "Perumpanarruppadai Sangam Verses on Blast Furnaces, Crucibles & Glowing Slag",
    "name_ta": "பெரும்பாணாற்றுப்படை இரும்பு உலைகள், மூசை மற்றும் எரியும் கசட்டுப் பாடல்கள்",
    "era": "Sangam Classical Era",
    "year_start": -200,
    "year_end": 100,
    "thinai": "mullai",
    "summary_en": "Perumpanarruppadai lines 205-215 and Purananuru 170 describing the pyrotechnic intensity of ancient Tamil blacksmith villages: glowing charcoal blast furnaces, bellows roaring through clay tuyeres, and sealed clay crucibles (Moosai) melting high-carbon steel.",
    "summary_ta": "பெரும்பாணாற்றுப்படை மற்றும் புறநானூற்றில் விவரிக்கப்படும் பண்டைய கொல்லர் உலைக்களக் காட்சிகள்: துருத்திகள் ஊதும் காற்றுத் தூம்புகள், எரியும் மரக்கரி, மற்றும் உருகும் எஃகைத் தாங்கும் சுடுமண் மூசைகளின் தீநெறி நுட்பம்.",
    "sources": [
      "Perumpanarruppadai 205-215",
      "Purananuru 170",
      "Srinivasan: Crucible Steel of South India"
    ],
    "content": "---\nid: text-perumpanarruppadai-iron-furnaces-and-crucible-poetry\ntitle: Perumpanarruppadai Sangam Verses on Blast Furnaces, Crucibles & Glowing Slag\ntype: text\nera: Sangam Classical Era (c. 200 BCE - 100 CE)\nthinai: mullai (Metallurgical Agronomy & Foundry Craft)\nstatus: canonical\n---\n\n# Perumpanarruppadai Sangam Verses on Blast Furnaces, Crucibles & Glowing Slag\n\n## 1. Classical Imagery of Foundry Villages\nIn *Perumpanarruppadai*, the wandering bard passes through the bustling artisan quarters of the northern Tamil pastoral country:\n> \"உலைக்களத்து அன்ன உருகெழு வெம்மை...\n> துருத்தி விம்மிய பொங்கு அழல் வெந்நீர்க்\n> கருங்கைக் கொல்லர் செந்தீ மூசை...\"\n*(The intense heat radiating like a blacksmith's hearth, where bellows heave air into leaping flames and dark-handed artisans handle sealed crucibles glowing in scarlet fire).*\n\n## 2. Technical Features Documented in Poetry\n1. **Thuruthi (துருத்தி)**: Twin animal-skin bellows operated by foot or hand to pump continuous forced drafts.\n2. **Moosai (மூசை)**: Closed refractory earthenware crucibles capable of withstanding the heat necessary to melt iron and carbon charges into crystalline steel.\n3. **Thoombu (தூம்பு)**: Cylindrical terracotta nozzle pipes that protected the leather bellows from furnace blow-back.\n"
  },
  {
    "file": "knowledge/inscriptions/insc-guttur-dharmapuri-crucible-steel-furnace-charters.md",
    "slug": "insc-guttur-dharmapuri-crucible-steel-furnace-charters",
    "category": "inscription",
    "name_en": "Guttur Dharmapuri Crucible Steel Industrial Excavation Charters",
    "name_ta": "குட்டூர் தருமபுரி மூசை எஃகு உருக்கு உலைக்கள அகழாய்வுக் குறிப்புகள்",
    "era": "Iron Age to Sangam Era",
    "year_start": -400,
    "year_end": 300,
    "thinai": "mullai",
    "summary_en": "Tamil Nadu State Department of Archaeology excavation records from Guttur in Dharmapuri documenting industrial-scale wootz steel manufacturing: clusters of sunken furnace pits, hundreds of conical rice-husk-tempered clay crucibles (Moosai), and vitrified tuyeres.",
    "summary_ta": "தருமபுரி மாவட்டம் குட்டூரில் தமிழ்நாடு அரசு தொல்லியல் துறையால் அகழப்பட்ட மாபெரும் எஃகு உருக்கு தொழிற்களம்; நூற்றுக்கணக்கான சுடுமண் மூசைகள், காற்றுத் தூம்புகள் மற்றும் உக்கன் எஃகுக் கட்டிகள் குறித்த ஆய்வுக் குறிப்புகள்.",
    "sources": [
      "TNSDA Excavation Report: Guttur & Mel-Siruvalur",
      "Srinivasan & Griffiths: South Indian Crucible Steel"
    ],
    "content": "---\nid: insc-guttur-dharmapuri-crucible-steel-furnace-charters\ntitle: Guttur Dharmapuri Crucible Steel Industrial Excavation Charters\ntype: inscription\nera: Iron Age to Sangam Era (c. 400 BCE - 300 CE)\nthinai: mullai (Industrial Archaeology & Metallurgy)\nstatus: canonical\n---\n\n# Guttur Dharmapuri Crucible Steel Industrial Excavation Charters\n\n## 1. Excavations at Guttur\nGuttur, situated near Pennagaram in Dharmapuri district, represents one of the largest ancient steel manufacturing centers discovered in southern India. \n\nExcavations revealed extensive industrial slag mounds (*Kollap-pattarai-medu*) spanning several hectares:\n- **Intact Crucibles**: Over 300 intact and fragmented refractory clay crucibles measuring 15–20 cm in height and 6–8 cm in outer diameter.\n- **Sunken Furnaces**: Circular earthen furnace hearths designed to hold 20 to 30 crucibles vertically packed around a central blast zone.\n- **Glassy Slag**: Vitrified dark green and purple fayalite-rich iron slag confirming temperatures exceeding 1350°C.\n"
  },
  {
    "file": "knowledge/inscriptions/insc-mel-siruvalur-megalithic-crucible-epigraphs.md",
    "slug": "insc-mel-siruvalur-megalithic-crucible-epigraphs",
    "category": "inscription",
    "name_en": "Mel-Siruvalur Megalithic Crucible Slag & Tuyere Excavation Records",
    "name_ta": "மேல்சிறுவளூர் பெருங்கற்கால மூசைக்கசடு மற்றும் தூம்பு அகழாய்வுப் பதிவுகள்",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": 200,
    "thinai": "mullai",
    "summary_en": "Excavation records from Mel-Siruvalur in Viluppuram district documenting stratified Iron Age forge levels with cylindrical terracotta tuyeres, high-refractory graphite-bearing clay crucibles, and high-carbon steel ingot remnants.",
    "summary_ta": "விழுப்புரம் மாவட்டம் மேல்சிறுவளூரில் கண்டறியப்பட்ட பெருங்கற்கால உருக்கு உலைகள், கிராபைட் பூசிய சுடுமண் மூசைகள் மற்றும் உருளை வடிவக் காற்றுத் தூம்புகள் குறித்த தொல்லியல் பதிவுகள்.",
    "sources": [
      "Srinivasan: Mel-Siruvalur Crucible Metallurgy",
      "Archaeological Survey of India Memoir No. 78"
    ],
    "content": "---\nid: insc-mel-siruvalur-megalithic-crucible-epigraphs\ntitle: Mel-Siruvalur Megalithic Crucible Slag & Tuyere Excavation Records\ntype: inscription\nera: Early Historic Era (c. 300 BCE - 200 CE)\nthinai: mullai (Iron Age Metallurgical Epigraphy)\nstatus: canonical\n---\n\n# Mel-Siruvalur Megalithic Crucible Slag & Tuyere Excavation Records\n\n## 1. Site Discovery and Stratigraphy\nMel-Siruvalur preserves an undisturbed sequence of Iron Age bloomery smelting transitioning into advanced crucible melting. \n\nThe site yielded unique evidence of **dual pyrotechnics**: primary bloomery reduction furnaces feeding sponge iron into secondary closed-crucible melting charges.\n\n## 2. Material Findings\n- **Crucible Fabric**: Highly carbonaceous, dark grey clay matrix mixed with crushed carbonaceous shale and organic rice husks.\n- **Tuyere Architecture**: Heavily vitrified, fireclay-coated tubular nozzles showing directional slag-droplet flow toward the furnace interior.\n"
  },
  {
    "file": "knowledge/concepts/concept-refractory-clay-crucible-modeling-and-rice-husk-temper-moosai.md",
    "slug": "concept-refractory-clay-crucible-modeling-and-rice-husk-temper-moosai",
    "category": "concept",
    "name_en": "Refractory Clay Crucible Modeling, Rice-Husk Temper & High-Silica Porosity Physics (Moosai)",
    "name_ta": "தீயெதிர்ப்பு களிமண் மூசை உருவாக்கம், உமிச் சாம்பல் கலவை மற்றும் சிலிக்கா நுண்துளை இயற்பியல்",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 400,
    "thinai": "mullai",
    "summary_en": "The refractory materials science of ancient Tamil wootz crucibles (Moosai): blending kaolinitic weathering clay with 20-30% organic rice husks. During firing, the husks char to combustible carbon and amorphous silica, creating a porous network that accommodates thermal shock and arrests crack propagation up to 1450°C.",
    "summary_ta": "கயோலின் களிமண்ணுடன் 20-30% நெல் உமியைக் கலந்து உருவாக்கப்பட்ட உக்கன் எஃகு மூசை; சுடும்போது உமி எரிந்து நுண்துளைகளையும் படிகமற்ற சிலிக்காவையும் உருவாக்கி 1450°C வெப்பத்திலும் வெடிக்காமல் தாங்கும் தீயெதிர்ப்புப் பொறியியல்.",
    "sources": [
      "Srinivasan: The Composition and Microstructure of Indian Crucible Steel",
      "Craddock: Early Metal Mining and Production",
      "Journal of Archaeological Science 1994"
    ],
    "content": "---\nid: concept-refractory-clay-crucible-modeling-and-rice-husk-temper-moosai\ntitle: Refractory Clay Crucible Modeling, Rice-Husk Temper & High-Silica Porosity Physics (Moosai)\ntype: concept\nera: Early Historic Era (c. 400 BCE - 400 CE)\nthinai: mullai (Refractory Materials Science & Pyrotechnics)\nstatus: canonical\n---\n\n# Refractory Clay Crucible Modeling, Rice-Husk Temper & High-Silica Porosity Physics (Moosai)\n\n## 1. The Challenge of Ultra-High Temperature Containment\nMelting steel requires sustaining internal temperatures of 1350°C to 1450°C for hours—temperatures at which ordinary earthenware clays melt into liquid slag.\n\nAncient Tamil pyrotechnologists resolved this by formulating a revolutionary **composite refractory material**:\n- **Matrix**: Highly aluminous kaolinitic refractory clay ($\\text{Al}_2\\text{Si}_2\\text{O}_5(\\text{OH})_4$).\n- **Temper**: 20% to 30% by volume of raw rice husks (*Nel-umi*).\n\n## 2. Microstructural Transformations During Firing\n1. **Carbonization**: When the sealed crucible is placed inside the reducing charcoal furnace, the organic husks pyrolyze into elemental carbon laths.\n2. **Amorphous Silica Release**: Rice husks naturally contain over 15–20% biogenic amorphous silica ($\\text{SiO}_2$). At high temperatures, this reacts with alumina to form needle-like **mullite crystals** ($3\\text{Al}_2\\text{O}_3 \\cdot 2\\text{SiO}_2$):\n   $$3(\\text{Al}_2\\text{O}_3 \\cdot 2\\text{SiO}_2) \\xrightarrow{\\Delta} 3\\text{Al}_2\\text{O}_3 \\cdot 2\\text{SiO}_2 + 4\\text{SiO}_2$$\n3. **Crack Deflection & Thermal Shock Resistance**: The microscopic planar voids left by charred husks arrest running thermal micro-cracks, preventing catastrophic rupture under thermal shock.\n"
  },
  {
    "file": "knowledge/concepts/concept-graphite-slip-coating-and-carbon-diffusion-barrier-mechanics.md",
    "slug": "concept-graphite-slip-coating-and-carbon-diffusion-barrier-mechanics",
    "category": "concept",
    "name_en": "Natural Flake Graphite Slip Linings, Slag Corrosion Resistance & Carbon Diffusion Mechanics",
    "name_ta": "இயற்கை கிராபைட் பூச்சு, கசட்டு அரிமான எதிர்ப்பு மற்றும் கார்பன் ஊடுருவல் கட்டுப்பாடு",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": 400,
    "thinai": "mullai",
    "summary_en": "The internal graphite slip technology applied to Tamil wootz crucibles: applying fine slurries of natural crystalline flake graphite onto the crucible interior to prevent corrosive FeO-rich liquid slag from dissolving the silica clay walls and precisely control carbon absorption into the molten iron.",
    "summary_ta": "மூசையின் உட்புறத்தில் பூசப்படும் இயற்கை கிராபைட் கூழ்மப் பூச்சு; உருகிய இரும்புக் கசடு களிமண் சுவர்களை அரிப்பதைத் தடுத்து, இரும்பினுள் கார்பன் சீராகக் கரைந்து உயர்ரக எஃகாக மாறுவதை ஒழுங்குபடுத்தும் வேதியியல் நுட்பம்.",
    "sources": [
      "Freestone & Tite: Refractories in the Ancient World",
      "Srinivasan: Wootz Crucible Internal Linings"
    ],
    "content": "---\nid: concept-graphite-slip-coating-and-carbon-diffusion-barrier-mechanics\ntitle: Natural Flake Graphite Slip Linings, Slag Corrosion Resistance & Carbon Diffusion Mechanics\ntype: concept\nera: Early Historic Era (c. 300 BCE - 400 CE)\nthinai: mullai (Interface Chemistry & Corrosion Physics)\nstatus: canonical\n---\n\n# Natural Flake Graphite Slip Linings, Slag Corrosion Resistance & Carbon Diffusion Mechanics\n\n## 1. Slag Corrosion Mechanics\nDuring high-temperature crucible steel melting, the primary threat to crucible containment is corrosive **fayalite slag** ($2\\text{FeO} \\cdot \\text{SiO}_2$). Liquid iron oxide vigorously attacks aluminosilicate refractory walls:\n$$\\text{FeO} + \\text{SiO}_2 \\rightarrow \\text{FeSiO}_3 \\text{ (low melting eutectic at 1178°C)}$$\n\nThis reaction can eat through a 15 mm crucible wall in under 30 minutes, resulting in furnace failure.\n\n## 2. Graphite Slip Protection\nTo counteract this, master crucible potters painted the interior with a slip of **flake graphite** mined from Dharwar schist belts:\n- **Chemical Inertness**: Crystalline graphite is non-wetting to molten slag and impervious to iron oxide attack.\n- **Controlled Carburization**: The graphite lining acts as a secondary solid-state carbon donor, steadily diffusing carbon atoms into the molten low-carbon wrought iron charge until it reaches the hyper-eutectoid steel threshold (1.2% to 1.6% C).\n"
  },
  {
    "file": "knowledge/concepts/concept-forced-draft-terracotta-tuyere-nozzle-aerodynamics-thoombu.md",
    "slug": "concept-forced-draft-terracotta-tuyere-nozzle-aerodynamics-thoombu",
    "category": "concept",
    "name_en": "Forced-Draft Terracotta Tuyere Nozzle Aerodynamics, Venturi Profiles & Blow-Back Protection (Thoombu)",
    "name_ta": "சுடுமண் காற்றுத் தூம்பு முனை பாய்ம இயக்கவியல், வெஞ்சுரி வடிவமைப்பு மற்றும் தீயெதிர் பாதுகாப்பு",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 400,
    "thinai": "mullai",
    "summary_en": "The aerodynamic and thermal engineering of smelting tuyeres (Thoombu): cylindrical and converging terracotta blast pipes inserted through furnace base walls to direct high-velocity forced air from bellows into the combustion zone while resisting extreme slag vitrification.",
    "summary_ta": "துருத்தியிலிருந்து வரும் காற்றை அதிவேகமாக உலைக்களத்தின் மையப் பகுதிக்குச் செலுத்தும் சுடுமண் காற்றுத் தூம்பு; வெஞ்சுரி தத்துவத்தின்படி காற்றழுத்தத்தை அதிகரித்து, உலைக்கசட்டு வெப்பத்தைத் துருத்திக்குச் செல்லாமல் தடுக்கும் பாய்மப் பொறியியல்.",
    "sources": [
      "Tylecote: The Early History of Metallurgy in Europe and Asia",
      "Bayley: Tuyeres in Iron Smelting"
    ],
    "content": "---\nid: concept-forced-draft-terracotta-tuyere-nozzle-aerodynamics-thoombu\ntitle: Forced-Draft Terracotta Tuyere Nozzle Aerodynamics, Venturi Profiles & Blow-Back Protection (Thoombu)\ntype: concept\nera: Early Historic Era (c. 400 BCE - 400 CE)\nthinai: mullai (Aerodynamics & High-Temperature Fluid Dynamics)\nstatus: canonical\n---\n\n# Forced-Draft Terracotta Tuyere Nozzle Aerodynamics, Venturi Profiles & Blow-Back Protection (Thoombu)\n\n## 1. Function of the Smelting Tuyere (*Thoombu*)\nThe **Thoombu** (tuyere) is the critical conduit connecting cold external bellows to the white-hot combustion core of the metallurgical furnace.\n\n### Structural Requirements:\n- **Wall Thickness**: 12–18 mm of refractory sandy clay.\n- **Bore Geometry**: Tapering internal diameter (contracting from 35 mm at the bellows inlet to 18–22 mm at the furnace nozzle tip).\n\n## 2. Aerodynamic Venturi Acceleration\nAs air from the heaving leather bellows is forced through the converging conical nozzle, its velocity increases inversely with the cross-sectional area:\n$$v_{\\text{exit}} = v_{\\text{inlet}} \\cdot \\left(\\frac{d_{\\text{inlet}}}{d_{\\text{exit}}}\\right)^2$$\n\nThis high-velocity air jet penetrates deep into the packed charcoal bed, creating an intensely localized oxidizing raceway zone where temperatures rapidly climb above 1400°C.\n\n## 3. Vitrification Gradient\nExcavated tuyeres demonstrate a distinct thermal gradient: while the nozzle tip protruding into the furnace is melted into green glassy vitrification, the rear 80% remains unaffected, shielding the delicate leather bellows from burning.\n"
  },
  {
    "file": "knowledge/concepts/concept-fourteen-hundred-degree-crucible-steel-thermal-furnace-insulation.md",
    "slug": "concept-fourteen-hundred-degree-crucible-steel-thermal-furnace-insulation",
    "category": "concept",
    "name_en": "Fourteen-Hundred Degree Crucible Steel Furnace Thermodynamics & Pit Insulation Architecture",
    "name_ta": "1400 டிகிரி மூசை எஃகு உலை வெப்ப இயக்கவியல் மற்றும் குழி உலைக் கட்டமைப்பு",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": 500,
    "thinai": "mullai",
    "summary_en": "The thermodynamics and chamber design of ancient Tamil wootz melting furnaces: sunken cylindrical pit hearths lined with refractory red clay and quartz sand, utilizing downward radiative heat transfer from incandescent hardwood charcoal to maintain 1400°C for hours with minimal heat loss.",
    "summary_ta": "செம்மண் மற்றும் குவார்ட்ஸ் மணல் பூசப்பட்ட தரைக்குழி உலைகளின் வெப்ப இயக்கவியல்; மரக்கரியின் கதிர்வீச்சு வெப்பத்தை வெளியேறாமல் தடுத்து 1400°C வெப்பநிலையை நிலைநிறுத்தி எஃகுக் கட்டிகளை உருக்கிய உலைக்களப் பொறியியல்.",
    "sources": [
      "Verhoeven: The Mystery of Damascus Blades (Scientific American)",
      "Srinivasan: Metallurgy of Wootz Steel Ingots"
    ],
    "content": "---\nid: concept-fourteen-hundred-degree-crucible-steel-thermal-furnace-insulation\ntitle: Fourteen-Hundred Degree Crucible Steel Furnace Thermodynamics & Pit Insulation Architecture\ntype: concept\nera: Early Historic Era (c. 300 BCE - 500 CE)\nthinai: mullai (Thermodynamics & Furnace Architecture)\nstatus: canonical\n---\n\n# Fourteen-Hundred Degree Crucible Steel Furnace Thermodynamics & Pit Insulation Architecture\n\n## 1. Thermodynamic Energy Balance\nTo fully liquefy hyper-eutectoid steel containing 1.4% carbon, the furnace interior must reach and hold at least **1350°C to 1420°C**.\n\nAt this temperature, heat loss via radiation scales with the fourth power of absolute temperature according to the Stefan-Boltzmann law:\n$$q_{\\text{rad}} = \\epsilon \\sigma (T_{\\text{hot}}^4 - T_{\\text{cold}}^4)$$\n\nWithout advanced insulating brickwork, furnaces would lose heat faster than charcoal combustion could supply it.\n\n## 2. Sunken Pit Construction Mechanics\n1. **Subterranean Installation**: Furnaces were excavated below ground level, using the surrounding dry earth as an infinite-mass insulating mantle ($\\kappa_{\\text{earth}} \\approx 0.5 - 0.8\\text{ W/m}\\cdot\\text{K}$).\n2. **Double Red-Clay Lining**: Internal walls were coated with three successive layers of refractory loam mixed with quartz sand, creating a ceramic radiant shield.\n3. **Slow Cooling Kinetics**: After melting, the furnace was not opened immediately; the air blasts were shut, allowing the crucibles to cool inside the insulated pit over 24 hours. This ultra-slow cooling produced the magnificent, coarse **dendritic cementite patterns** characteristic of genuine wootz steel.\n"
  },
  {
    "file": "knowledge/characters/char-guttur-master-crucible-maker-moosai-kuyavan.md",
    "slug": "char-guttur-master-crucible-maker-moosai-kuyavan",
    "category": "character",
    "name_en": "Master Refractory Potter & Crucible Modeler: Moosai Kuyavan of Guttur",
    "name_ta": "குட்டூர் தலைமைத் தீயெதிர்ப்பு மூசைச் சிற்பக் குயவர்",
    "era": "Iron Age to Sangam Era",
    "year_start": -300,
    "year_end": -100,
    "thinai": "mullai",
    "summary_en": "The hereditary master potter of Guttur in the Dharmapuri iron belt who developed the rice-husk kaolin composite formula, hand-pinched conical crucibles, and formulated airtight refractory lids for wootz steel foundries.",
    "summary_ta": "தருமபுரி குட்டூர் உலைக்களங்களுக்குத் தேவையான அதிவெப்பம் தாங்கும் சுடுமண் மூசைகளை நெல் உமி மற்றும் களிமண் கொண்டு வார்த்தளித்த தலைசிறந்த மட்பாண்ட வேதியியலாளர்.",
    "sources": [
      "Guttur Excavation Reports",
      "Traditional Metallurgical Crafts of Tamilakam"
    ],
    "content": "---\nid: char-guttur-master-crucible-maker-moosai-kuyavan\ntitle: Master Refractory Potter & Crucible Modeler: Moosai Kuyavan of Guttur\ntype: character\nera: Iron Age to Sangam Era (c. 300 - 100 BCE)\nthinai: mullai (Ceramic Materials Craft)\nstatus: canonical\n---\n\n# Master Refractory Potter & Crucible Modeler: Moosai Kuyavan of Guttur\n\n## 1. Professional Status\nWorking in symbiotic partnership with master swordsmiths and iron smelters, the **Moosai Kuyavan** was the unsung scientific foundation of Tamil wootz steel hegemony.\n\n## 2. Artisanal Formulas\n- **Husk Retting**: Soaking rice husks in stagnant water for two weeks to soften lignins before blending into clay.\n- **Lid Sealing (*Moosai-Vaai-Kattal*)**: Luting conical clay caps onto loaded crucibles with a sticky refractory slurry of river silt and cattle dung that vitrified during the first minutes of furnace heating, sealing the charge in an airtight reducing pocket.\n"
  },
  {
    "file": "knowledge/characters/char-mel-siruvalur-furnace-tuyere-artisan-thoombu-kollan.md",
    "slug": "char-mel-siruvalur-furnace-tuyere-artisan-thoombu-kollan",
    "category": "character",
    "name_en": "Blast Nozzle Turner & Forge Pipe Specialist: Thoombu Kollan of Mel-Siruvalur",
    "name_ta": "மேல்சிறுவளூர் காற்றுத் தூம்பு வடிவமைப்பாளர் மற்றும் உலைக்களக் கொல்லர்",
    "era": "Early Historic Era",
    "year_start": -200,
    "year_end": 50,
    "thinai": "mullai",
    "summary_en": "The specialist foundry metalsmith of Mel-Siruvalur who fabricated aerodynamically tapered fireclay tuyeres and coordinated multi-bellows air blasts to maintain intense 1400°C furnace melting cores.",
    "summary_ta": "உலைக்களங்களுக்குத் தேவையான காற்றுப் பாயும் சுடுமண் தூம்புகளைச் சீராக வடிவமைத்து, பல துருத்திகளை ஒருங்கிணைத்து வெப்பநிலையை 1400°C வரை உயர்த்திய உலைக்கள நுட்பாளர்.",
    "sources": [
      "Mel-Siruvalur Archaeometallurgy Survey",
      "South Indian Iron Smelting Traditions"
    ],
    "content": "---\nid: char-mel-siruvalur-furnace-tuyere-artisan-thoombu-kollan\ntitle: Blast Nozzle Turner & Forge Pipe Specialist: Thoombu Kollan of Mel-Siruvalur\ntype: character\nera: Early Historic Era (c. 200 BCE - 50 CE)\nthinai: mullai (Foundry Pyrotechnics)\nstatus: canonical\n---\n\n# Blast Nozzle Turner & Forge Pipe Specialist: Thoombu Kollan of Mel-Siruvalur\n\n## 1. Role in the Smelting Hierarchy\nThe **Thoombu Kollan** was responsible for the fluid-dynamic heart of the furnace. A poorly aligned or cracked tuyere would allow burning charcoal to enter the bellows or cool the melting crucible, ruining an entire day's batch.\n\n## 2. Precision Skills\n- Hand-rolling uniform clay tubes around oiled wooden mandrels.\n- Inspecting nozzle vitreous flow during active smelting and replacing eroded tuyere tips mid-heat without dropping furnace temperatures.\n"
  },
  {
    "file": "knowledge/places/place-guttur-ancient-crucible-furnace-haven.md",
    "slug": "place-guttur-ancient-crucible-furnace-haven",
    "category": "place",
    "name_en": "Guttur: Ancient Crucible Steel Foundry Haven & Dharmapuri Iron Basin",
    "name_ta": "குட்டூர் - பண்டைய மூசை எஃகு தொழிற்பட்டினம் மற்றும் தருமபுரி இரும்புப் படுகை",
    "era": "Iron Age to Sangam Era",
    "year_start": -500,
    "year_end": 400,
    "thinai": "mullai",
    "summary_en": "Landmark archaeometallurgical site in the Dharmapuri iron belt celebrated for extensive slag mounds, sunken wootz steel melting furnaces, thousands of refractory crucibles (Moosai), and continuous high-temperature steel production supplying ancient global sword markets.",
    "summary_ta": "தருமபுரி இரும்புத்தாதுப் படுகையில் அமைந்துள்ள வரலாற்றுப் புகழ்பெற்ற எஃகு உருக்குத் தளம்; உலகப் புகழ்பெற்ற உக்கன் எஃகுக் கட்டிகள் மற்றும் ஆயிரக்கணக்கான மூசைகளை வெளிப்படுத்திய முதன்மைத் தொல்லியல் களம்.",
    "sources": [
      "TNSDA Excavation Reports",
      "Srinivasan: High-Carbon Steel of Dharmapuri",
      "District Gazetteer of Dharmapuri"
    ],
    "content": "---\nid: place-guttur-ancient-crucible-furnace-haven\ntitle: Guttur: Ancient Crucible Steel Foundry Haven & Dharmapuri Iron Basin\ntype: place\nera: Iron Age to Sangam Era (c. 500 BCE - 400 CE)\nthinai: mullai (Metallurgical Geography & Industrial Archaeology)\nstatus: canonical\n---\n\n# Guttur: Ancient Crucible Steel Foundry Haven & Dharmapuri Iron Basin\n\n## 1. Topography & Geological Wealth\n**Guttur** (lat 12.1800° N, lng 78.1000° E) lies in the mineral-rich crystalline uplands of Dharmapuri in northwestern Tamil Nadu. \n\nThe site is flanked by massive quartz-magnetite hill ranges that yielded exceptionally pure iron ores (exceeding 60% Fe), while the adjacent dry deciduous forests provided limitless hardwood charcoal (*Karungali* and *Vengai*) required for sustained furnace operation.\n\n## 2. Archaeological Significance\nArchaeological excavations confirmed that Guttur was an industrial city-scale wootz steel production center, exporting standardized cast high-carbon steel cakes along the Kaveri river trade arterial to Roman, Persian, and Mediterranean empires.\n"
  }
]
EDGES = [
  [
    "text-perumpanarruppadai-iron-furnaces-and-crucible-poetry",
    "celebrates_crucible_foundries",
    "concept-refractory-clay-crucible-modeling-and-rice-husk-temper-moosai",
    "cultural",
    "Sangam Classical Era",
    "Perumpanarruppadai verses describing glowing clay crucibles and roaring furnaces",
    "Perumpanarruppadai 205-215"
  ],
  [
    "insc-guttur-dharmapuri-crucible-steel-furnace-charters",
    "documents_excavated_crucibles_at",
    "place-guttur-ancient-crucible-furnace-haven",
    "archaeological",
    "Iron Age to Sangam Era",
    "Excavations unearthing hundreds of wootz steel crucibles and tuyeres",
    "TNSDA Guttur"
  ],
  [
    "insc-mel-siruvalur-megalithic-crucible-epigraphs",
    "records_graphite_linings_in",
    "concept-graphite-slip-coating-and-carbon-diffusion-barrier-mechanics",
    "archaeological",
    "Early Historic Era",
    "Stratified excavation of graphite-coated refractory crucibles",
    "ASI Memoir 78"
  ],
  [
    "concept-refractory-clay-crucible-modeling-and-rice-husk-temper-moosai",
    "lined_with_graphite_slip",
    "concept-graphite-slip-coating-and-carbon-diffusion-barrier-mechanics",
    "technological",
    "Early Historic Era",
    "Graphite slip applied to rice-husk-tempered clay crucible walls",
    "Srinivasan 1994"
  ],
  [
    "concept-forced-draft-terracotta-tuyere-nozzle-aerodynamics-thoombu",
    "injects_forced_air_into",
    "concept-fourteen-hundred-degree-crucible-steel-thermal-furnace-insulation",
    "technological",
    "Early Historic Era",
    "Converging tuyere nozzles creating 1400°C combustion raceway",
    "Tylecote 1992"
  ],
  [
    "concept-fourteen-hundred-degree-crucible-steel-thermal-furnace-insulation",
    "sustains_melting_inside",
    "concept-refractory-clay-crucible-modeling-and-rice-husk-temper-moosai",
    "pyrotechnic",
    "Early Historic Era",
    "Sunken furnace pit holding 30 closed crucibles at melting temperature",
    "Verhoeven 2001"
  ],
  [
    "char-guttur-master-crucible-maker-moosai-kuyavan",
    "shaped_refractory_crucibles_at",
    "place-guttur-ancient-crucible-furnace-haven",
    "social",
    "Iron Age to Sangam Era",
    "Master potter crafting composite rice-husk kaolin crucibles",
    "Dharmapuri Survey"
  ],
  [
    "char-mel-siruvalur-furnace-tuyere-artisan-thoombu-kollan",
    "engineered_tuyere_nozzles",
    "concept-forced-draft-terracotta-tuyere-nozzle-aerodynamics-thoombu",
    "technological",
    "Early Historic Era",
    "Turning high-refractory fireclay tuyeres for iron smelting furnaces",
    "Mel-Siruvalur"
  ],
  [
    "char-guttur-master-crucible-maker-moosai-kuyavan",
    "sealed_crucibles_with",
    "concept-graphite-slip-coating-and-carbon-diffusion-barrier-mechanics",
    "technological",
    "Iron Age to Sangam Era",
    "Luting airtight refractory lids and painting graphite slip linings",
    "Indian Crucible Steel"
  ],
  [
    "concept-fourteen-hundred-degree-crucible-steel-thermal-furnace-insulation",
    "operated_at_scale_in",
    "place-guttur-ancient-crucible-furnace-haven",
    "industrial",
    "Iron Age to Sangam Era",
    "Sunken furnace hearths and slag mounds across the Dharmapuri iron basin",
    "Guttur Report"
  ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 22 Corpus 1: Crucible Steel Pyrotechnics & Tuyeres into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 22 Corpus 1: Crucible Steel Pyrotechnics & Tuyeres Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
