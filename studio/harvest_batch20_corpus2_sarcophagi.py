#!/usr/bin/env python3
import os
import sys
import json
import uuid
import psycopg2
import requests

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
MOOLAM_KNOWLEDGE = "/mnt/h/DevTools/Projects/learn-ai/moolam-chronicles/knowledge"

DOSSIERS = [
  {
    "file": "knowledge/texts/text-manimekalai-funerary-burial-types-and-sarcophagi-poetry.md",
    "slug": "text-manimekalai-funerary-burial-types-and-sarcophagi-poetry",
    "category": "text",
    "name_en": "Manimekalai Funerary Typology: Sarcophagi, Cist Vaults & Megalithic Burial Poetry",
    "name_ta": "மணிமேகலை ஈம அடக்க வகைப் பாடல்கள்: ஈமப்பேழை, கல்திட்டை மற்றும் முதுமக்கள் தாழி",
    "era": "Post-Sangam Classical Era",
    "year_start": 200,
    "year_end": 500,
    "thinai": "marutham",
    "summary_en": "Manimekalai Canto 6 (Chakkaravalak-kottam) documenting the classical fivefold categorization of ancient Tamil funerary practices: cremation (Suduvor), burial in pits (Iduvor), stone cist vaulting (Thodukuzhi-Paduppor), subterranean rock entombment (Izhai-vayin-Aadaippor), and urn/sarcophagus internment (Thaazhiyin-Kavippor).",
    "summary_ta": "சக்கரவாளக் கோட்டத்து மணிமேகலை காதை 6-ல் விவரிக்கப்படும் பண்டைத் தமிழரின் ஐவகை ஈமச் சடங்குகள்: சுடுவோர், இடுவோர், தொடுகூழிப் படுப்போர், இழைவயின் அடைப்போர் மற்றும் தாழியின் கவிப்போர் (ஈமப்பேழை அடக்கம்) குறித்த அரிய இலக்கியப் பதிவு.",
    "sources": [
      "Manimekalai 6:64-70",
      "Rajan: Megalithic Funerary Architecture of Tamil Nadu",
      "Champakalakshmi: Archaeology & Sangam Literature"
    ],
    "content": "---\nid: text-manimekalai-funerary-burial-types-and-sarcophagi-poetry\ntitle: Manimekalai Funerary Typology: Sarcophagi, Cist Vaults & Megalithic Burial Poetry\ntype: text\nera: Post-Sangam Classical Era (c. 200 - 500 CE)\nthinai: marutham (Civilizational Eschatology)\nstatus: canonical\n---\n\n# Manimekalai Funerary Typology: Sarcophagi, Cist Vaults & Megalithic Burial Poetry\n\n## 1. The Classical Funerary Taxonomy of Manimekalai\nIn the celebrated Tamil Buddhist epic *Manimekalai*, composed by the grain merchant-poet Seethalai Sathanar, Canto 6 provides the most comprehensive literary classification of Megalithic burial customs preserved from ancient South Asia:\n\n> \"சுடுவோர் இடுவோர் தொடுகுழிப் படுப்போர்\n> இழைவயின் அடைப்போர் தாழியிற் கவிப்போர்\n> என்றுஇவை எல்லாம் இயைந்த இடமாகி...\"\n*(Those who cremate; those who expose to the elements; those who place the dead in scooped-out pits; those who entomb them in stone cist chambers; and those who cover them in urns and legged sarcophagi—such was the great burial ground of Chakkaravalak-kottam).*\n\n## 2. Archaeological Correlation with Megalithic Typology\nThis poetic inventory matches the archaeological taxonomy established by 20th-century surveys:\n1. **Suduvor (சுடுவோர்)**: Primary cremation pyres.\n2. **Iduvor (இடுவோர்)**: Excarnation or open-air exposure before secondary collection of bones.\n3. **Thodukuzhi-Paduppor (தொடுகுழிப் படுப்போர்)**: Simple earthen pit burials or stone-lined grave trenches.\n4. **Izhai-vayin-Aadaippor (இழைவயின் அடைப்போர்)**: Granitic megalithic dolmens and orthostat cists (*Korangupattadai*).\n5. **Thaazhiyin-Kavippor (தாழியிற் கவிப்போர்)**: Giant pyriform terracotta urn burials (*Emathaali*) and multi-legged terracotta sarcophagi (*Kavikkal*).\n\n## 3. Socio-Religious Eschatology\nThe text reflects a cosmopolitan early historic society where ancestral Megalithic commemorative practices coexisted with Vedic cremation and Buddhist/Jaina philosophical attitudes toward the impermanence of the physical body.\n"
  },
  {
    "file": "knowledge/inscriptions/insc-paiyampalli-megalithic-burial-complex-epigraphs.md",
    "slug": "insc-paiyampalli-megalithic-burial-complex-epigraphs",
    "category": "inscription",
    "name_en": "Paiyampalli Megalithic Terracotta Sarcophagi & Iron Implement Excavation Charters",
    "name_ta": "பையம்பள்ளி பெருங்கற்கால ஈமப்பேழை மற்றும் இரும்புக் கருவி அகழாய்வுக் குறிப்புகள்",
    "era": "Iron Age to Sangam Era",
    "year_start": -1000,
    "year_end": -300,
    "thinai": "kurinji",
    "summary_en": "Archaeological excavation inscriptions and radiocarbon reports from Paiyampalli in the Palar valley documenting stratified Megalithic habitation levels, terracotta legged sarcophagi, iron slag furnaces, and pristine socketed iron axes dating to the early 1st millennium BCE.",
    "summary_ta": "திருப்பத்தூர் பாலாற்றுப் பள்ளத்தாக்கில் அமைந்துள்ள பையம்பள்ளியில் இந்தியத் தொல்பொருள் ஆய்வுத் துறையால் கண்டறியப்பட்ட கால்வைத்த சுடுமண் ஈமப்பேழைகள், இரும்பு உருக்கு உலைகள் மற்றும் கி.மு. 1000 காலத்திய தொல்லியல் சான்றுகள்.",
    "sources": [
      "Indian Archaeology: A Review (IAR 1964-65, 1967-68)",
      "ASI Excavation Memoir: Paiyampalli",
      "Rao: Iron Age in South India"
    ],
    "content": "---\nid: insc-paiyampalli-megalithic-burial-complex-epigraphs\ntitle: Paiyampalli Megalithic Terracotta Sarcophagi & Iron Implement Excavation Charters\ntype: inscription\nera: Iron Age to Sangam Era (c. 1000 - 300 BCE)\nthinai: kurinji (Megalithic Metallurgy & Excavation Stratigraphy)\nstatus: canonical\n---\n\n# Paiyampalli Megalithic Terracotta Sarcophagi & Iron Implement Excavation Charters\n\n## 1. Site Geography & Discovery\nLocated in the Tirupattur taluk of northern Tamil Nadu, **Paiyampalli** is nestled at the base of the Javadi hills along the Palar river drainage. Excavated under S.R. Rao for the Archaeological Survey of India (ASI) in 1964–1968, it remains one of the landmark stratigraphical type-sites for South Indian protohistory.\n\n## 2. Archaeological Stratigraphy & Findings\n- **Period I (Neolithic)**: Coarse grey and red ware, ground stone celts, bone points.\n- **Period II (Megalithic / Iron Age)**: Radiocarbon dated to c. 1000–300 BCE. Characterized by:\n  1. **Multi-Legged Terracotta Sarcophagi**: Elongated bathtub-shaped burial coffins supported by 8, 10, or 12 hollow cylindrical terracotta legs.\n  2. **Associated Grave Assemblages**: Conical lids, black-and-red ware (*BRW*) tulip bowls, and perforated ring stands.\n  3. **High-Carbon Iron Implements**: Socketed sickles, chisels, arrowheads, and iron tridents (*Sulam*) deposited directly beside the skeletal remains inside the sarcophagus.\n\n## 3. Radiocarbon Dating Significance\nPaiyampalli provided the foundational carbon-14 dates (TF-828: $3160 \\pm 105\\text{ BP}$, c. 1200–1000 BCE) proving that the Megalithic transition, terracotta sarcophagus ceramic craft, and iron pyrotechnology were well established in Tamil Nadu centuries before early imperial dynastic histories.\n"
  },
  {
    "file": "knowledge/inscriptions/insc-sanur-megalithic-sarcophagus-and-dolmenoid-cist-charters.md",
    "slug": "insc-sanur-megalithic-sarcophagus-and-dolmenoid-cist-charters",
    "category": "inscription",
    "name_en": "Sanur Megalithic Legged Sarcophagus & Dolmenoid Cist Archaeological Inscriptions",
    "name_ta": "சானூர் பெருங்கற்காலக் கால்வைத்த ஈமப்பேழை மற்றும் கல்திட்டைத் தொல்பொருள் பதிவுகள்",
    "era": "Iron Age to Sangam Era",
    "year_start": -800,
    "year_end": -200,
    "thinai": "mullai",
    "summary_en": "Archaeological Survey of India excavation records at Sanur near Madurantakam detailing intact dolmenoid cists enclosing multi-legged terracotta sarcophagi adorned with zoomorphic terracotta lids, iron weapons, and intact skeletal post-cranial deposits.",
    "summary_ta": "செங்கல்பட்டு அருகே சானூரில் அகழப்பட்ட பெருங்கற்கால கல்திட்டைகள், அவற்றுள் புதைக்கப்பட்ட பல்கால் சுடுமண் ஈமப்பேழைகள் மற்றும் விலங்குருவ மூடிகள் குறித்த இந்தியத் தொல்லியல் துறை விரிவான ஆய்வுப் பதிவுகள்.",
    "sources": [
      "Banerjee & Soundara Rajan: Sanur 1950-1952 (Ancient India No. 15)",
      "ASI Memoirs on Megalithic Cists"
    ],
    "content": "---\nid: insc-sanur-megalithic-sarcophagus-and-dolmenoid-cist-charters\ntitle: Sanur Megalithic Legged Sarcophagus & Dolmenoid Cist Archaeological Inscriptions\ntype: inscription\nera: Iron Age to Sangam Era (c. 800 - 200 BCE)\nthinai: mullai (Megalithic Chamber Architecture)\nstatus: canonical\n---\n\n# Sanur Megalithic Legged Sarcophagus & Dolmenoid Cist Archaeological Inscriptions\n\n## 1. Excavation Overview at Sanur\nSanur, situated near Madurantakam in Chengalpattu district, comprises an extensive necropolis of over 300 megalithic monuments. Excavated by N.R. Banerjee and K.V. Soundara Rajan for the ASI, it revealed exceptional architectural preservation of **dolmenoid cists containing terracotta sarcophagi**.\n\n## 2. Structural Morphology of Megalith Meg. V\nThe excavation of *Megalith V* exposed:\n1. **Boulder Circle**: An exterior ring of massive granite boulders measuring 12 meters in diameter.\n2. **Cap-Stone & Chamber**: A massive flat granite capstone covering a subterranean rectangular cist formed by upright stone slabs (*orthostats*).\n3. **Internal Sarcophagus**: Resting on the granite floor was a terracotta sarcophagus supported by **15 hollow terracotta legs** arranged in three parallel rows of five.\n4. **Grave Inventory**: Over 70 pottery vessels including ring-stands, chalices, and bowls in Black-and-Red Ware, along with heavy iron swords, daggers, and horse-bits.\n\n## 3. Anthropological Insights\nThe skeletal remains inside the Sanur sarcophagi represented secondary, fractional excarnated interments—selected long bones and skulls deposited after ceremonial ritual defleshing.\n"
  },
  {
    "file": "knowledge/concepts/concept-multi-legged-terracotta-sarcophagus-molding-and-firing-kavikkal.md",
    "slug": "concept-multi-legged-terracotta-sarcophagus-molding-and-firing-kavikkal",
    "category": "concept",
    "name_en": "Multi-Legged Terracotta Sarcophagus Modeling, Grooved Lip Jointing & Kiln Firing Pyrotechnics (Kavikkal)",
    "name_ta": "பல்கால் சுடுமண் ஈமப்பேழை (கவிக்கல்) வார்ப்பு, விளிம்புப் பொருத்து மற்றும் சுடுநெறி நுட்பம்",
    "era": "Iron Age to Sangam Era",
    "year_start": -1000,
    "year_end": 300,
    "thinai": "marutham",
    "summary_en": "The ceramic engineering of ancient Tamil legged sarcophagi (Kavikkal): coil-built clay troughs with rolled grooved rims, fitted with 8 to 15 hollow conical support legs with ventilation apertures, slowly dried and fired in pit kilns under controlled oxidizing-reducing thermal conditions.",
    "summary_ta": "களிமண் உருளைகளை அடுக்கி வடிவமைக்கப்பட்ட தொட்டி போன்ற ஈமப்பேழை; 8 முதல் 15 வரையான காற்றோட்டத் துளைகளுடன் கூடிய சுடுமண் கால்கள், விளிம்புப் பூட்டுகள் மற்றும் வெடிப்பு ஏற்படாமல் கட்டுப்படுத்தப்பட்ட குழி உலைகளில் சுடப்பட்ட பண்டைய மட்பாண்டப் பொறியியல்.",
    "sources": [
      "Rajan: Iron Age Crafts & Ceramic Pyrotechnics",
      "Saraswati: Pottery Techniques of Peasant India",
      "Ancient India Journal Vol. 15"
    ],
    "content": "---\nid: concept-multi-legged-terracotta-sarcophagus-molding-and-firing-kavikkal\ntitle: Multi-Legged Terracotta Sarcophagus Modeling, Grooved Lip Jointing & Kiln Firing Pyrotechnics (Kavikkal)\ntype: concept\nera: Iron Age to Sangam Era (c. 1000 BCE - 300 CE)\nthinai: marutham (Ceramic Civil Engineering & Pyrotechnics)\nstatus: canonical\n---\n\n# Multi-Legged Terracotta Sarcophagus Modeling, Grooved Lip Jointing & Kiln Firing Pyrotechnics (Kavikkal)\n\n## 1. Anatomy of the Sarcophagus (*Kavikkal*)\nThe terracotta sarcophagus (referred to in local epigraphical parlance as *Kavikkal* or *Ema-Thotti*) is a monumental ceramic coffin engineered to house human remains and funerary offerings.\n\n### Dimensions & Structure:\n- **Length**: 1.5 to 2.2 meters (accommodating extended or crouched burials).\n- **Width**: 0.45 to 0.7 meters; **Depth**: 0.35 to 0.5 meters.\n- **Support Legs**: 8, 10, 12, or 15 hollow, wheel-thrown conical or cylindrical clay pedestals luted onto the underside of the trough while the clay is leather-hard.\n\n## 2. Fabrication Methodology\n1. **Clay Levigation**: Heavy alluvial clay tempered with river sand, crushed pottery grog, and rice husks to minimize shrinkage during drying.\n2. **Coil & Slab Building**: Artisans layered thick clay coils upon a wooden former mold, beating the walls with wooden paddles (*Thattu-palagai*) to compress air pockets.\n3. **Perforated Leg Fitting**: Each hollow leg was punctured with a small round vent-hole (10–15 mm) to permit trapped air and steam to escape during firing, preventing catastrophic explosive thermal cracking:\n   $$P_{\\text{steam}} \\propto \\frac{n R T}{V_{\\text{void}}}$$\n4. **Grooved Lipping**: The upper perimeter was sculpted with an internal flange or recessed lip to seat the matching vaulted terracotta lid (*Kavippu*).\n\n## 3. Kiln Firing Pyrotechnics\nBecause of their enormous mass (exceeding 80–120 kg dry weight), sarcophagi could not be fired in ordinary pottery kilns. They were embedded in large circular open pit kilns (*Medu-soolai*) blanketed with dried cow-dung cakes, straw, and slow-burning hardwood charcoal. \n\nFiring proceeded gradually over 48 to 72 hours, reaching soak temperatures of 700–850°C to achieve full vitrification without thermal shock deformation.\n"
  },
  {
    "file": "knowledge/concepts/concept-zoomorphic-ram-and-elephant-funerary-lid-sculpture.md",
    "slug": "concept-zoomorphic-ram-and-elephant-funerary-lid-sculpture",
    "category": "concept",
    "name_en": "Zoomorphic Ram, Bull & Elephant Terracotta Sarcophagus Lid Sculptural Iconography",
    "name_ta": "விலங்குருவ ஆட்டுக்கடா, காளை மற்றும் யானை ஈமப்பேழை மூடிச் சிற்பக் கலை",
    "era": "Iron Age to Sangam Era",
    "year_start": -800,
    "year_end": 200,
    "thinai": "kurinji",
    "summary_en": "The zoomorphic terracotta lids of ancient Tamil Megalithic sarcophagi: sculpted with naturalistic heads of horned rams, humped bulls, and tusker elephants at one terminal, functioning as totemic guardians and symbolic vehicles (Vahanas) guiding ancestral souls to the otherworld.",
    "summary_ta": "பண்டைய தமிழக ஈமப்பேழைகளின் சுடுமண் மூடிகள் மீது வடிக்கப்பட்ட ஆட்டுக்கடா, திமில் காளை மற்றும் யானைத் தலைச் சிற்பங்கள்; மூதாதையர் ஆன்மாவை மறுவுலகுக்கு வழிநடத்தும் குலக்குறிக் காவலர்களாக விளங்கிய சிற்பக்கலை நுட்பம்.",
    "sources": [
      "Rea: Catalogue of Prehistoric Antiquities (ASI 1915)",
      "Ancient India Vol. 15",
      "Nagaswamy: Art & Archaeology of Tamil Nadu"
    ],
    "content": "---\nid: concept-zoomorphic-ram-and-elephant-funerary-lid-sculpture\ntitle: Zoomorphic Ram, Bull & Elephant Terracotta Sarcophagus Lid Sculptural Iconography\ntype: concept\nera: Iron Age to Sangam Era (c. 800 BCE - 200 CE)\nthinai: kurinji (Funerary Terracotta Art & Eschatology)\nstatus: canonical\n---\n\n# Zoomorphic Ram, Bull & Elephant Terracotta Sarcophagus Lid Sculptural Iconography\n\n## 1. Iconographic Typology\nWhile many Megalithic sarcophagi featured simple vaulted, boat-shaped, or gabled terracotta covers, specialized elite burials incorporated **zoomorphic terminal sculptures** integrated into the lid:\n- **Horned Ram (ஆட்டுக்கடா)**: Distinct curved spiraled horns, incised facial textures, and prominent eye appliqués, notably documented at Sankavaram and Sanur.\n- **Humped Zebu Bull (திமில் காளை)**: Muscular neck hump, forward-pointing horns, representing pastoralist prosperity and clan vitality.\n- **Tusker Elephant (யானை)**: Flared ears, elongated trunk curling downward to touch the sarcophagus rim.\n\n## 2. Sculptural Technique\nThe animal heads were modeled hollow using the pinch-and-coil method. Details such as dewlaps, horn ridges, and harness straps were applied via **appliqué clay fillets** and decorated with comb-stamped punctations and fingertip impressions before firing.\n\n## 3. Symbolic Meaning & Eschatological Function\nIn Sangam eschatological belief, animals served as clan totems and psychopomps—spiritual conductors guiding the deceased chieftain (*Koman*) across the river of death into the realm of the ancestors (*Marumai*). The zoomorphic sarcophagus converted the grave into a symbolic ceremonial chariot or barge carrying the hero into immortality.\n"
  },
  {
    "file": "knowledge/concepts/concept-black-and-red-ware-funerary-vessels-and-iron-weapon-offerings.md",
    "slug": "concept-black-and-red-ware-funerary-vessels-and-iron-weapon-offerings",
    "category": "concept",
    "name_en": "Black-and-Red Ware Grave Goods, Socketed Iron Axes, Tridents & Funerary Urn Metallurgical Deposits",
    "name_ta": "கருப்பு-சிவப்பு ஈம மட்பாண்டங்கள், துளையிட்ட இரும்புக் கோடாரிகள் மற்றும் சூலப் படையல்கள்",
    "era": "Iron Age to Sangam Era",
    "year_start": -1000,
    "year_end": 200,
    "thinai": "mullai",
    "summary_en": "The ritual deposition of grave offerings accompanying Megalithic sarcophagi: inverted-fired Black-and-Red Ware (BRW) bowls containing food/liquids, ring stands, and high-carbon iron implements including socketed hoes, battleaxes, horse snaffles, and multi-pronged tridents (Sulam).",
    "summary_ta": "ஈமப்பேழை மற்றும் தாழிகளுடன் புதைக்கப்பட்ட தலைகீழ் சுடுநெறிக் கருப்பு-சிவப்பு மட்பாண்டங்கள், உணவுப் படையல்கள், மற்றும் போர்க்கருவிகளான துளையிட்ட இரும்புக் கோடாரிகள், வாள்கள் மற்றும் இரும்புச் சூலங்களின் உலோகவியல் தொகுப்பு.",
    "sources": [
      "Wheeler: Brahmagiri & Chandravalli (Ancient India No. 4)",
      "Rajan: Iron Age Archaeology of South India",
      "Adichanallur ASI Excavation Reports"
    ],
    "content": "---\nid: concept-black-and-red-ware-funerary-vessels-and-iron-weapon-offerings\ntitle: Black-and-Red Ware Grave Goods, Socketed Iron Axes, Tridents & Funerary Urn Metallurgical Deposits\ntype: concept\nera: Iron Age to Sangam Era (c. 1000 BCE - 200 CE)\nthinai: mullai (Metallurgical Depositional Archaeology)\nstatus: canonical\n---\n\n# Black-and-Red Ware Grave Goods, Socketed Iron Axes, Tridents & Funerary Urn Metallurgical Deposits\n\n## 1. The Inverted Firing Physics of Black-and-Red Ware (BRW)\nEvery Megalithic sarcophagus in Tamil Nadu is invariably accompanied by dozens of **Black-and-Red Ware (BRW)** vessels:\n- **Pyrotechnic Mechanism**: The vessel is placed upside-down inside the kiln. The interior and rim are deprived of oxygen, creating a reducing environment where ferric oxide ($Fe_2O_3$) reduces to black ferrous oxide ($FeO$) and carbon soot penetrates the clay pores:\n  $$\\text{Fe}_2\\text{O}_3 + \\text{CO} \\rightarrow 2\\text{FeO} + \\text{CO}_2$$\n- The exterior body is exposed to free air circulation, oxidizing to a brilliant burnished red.\n\n## 2. Funerary Metallurgical Weapon Deposits\nBeside the terracotta sarcophagus, excavators encounter deliberate ritual placements of forged iron implements:\n1. **Socketed Axes (*Kuzhai-Kodarigal*)**: Heavy forestry and combat axes with folded cylindrical sockets for hafting hardwood handles.\n2. **Iron Tridents (*Sulam*)**: Three-pronged ceremonial weapons measuring up to 1.5 meters, symbolizing martial authority and early Murugan iconography.\n3. **Horse-Bits (*Kuthirai-Kadi-vaalam*)**: Snaffle bits with rigid cheek-pieces, confirming the presence of elite cavalry chieftains in northern Tamil Nadu.\n\n## 3. Ritual \"Killing\" of Weapons\nMany iron swords and spearheads were intentionally bent double or broken before placement in the grave, a widespread Megalithic ritual practice intended to \"kill\" the weapon's spirit so it could accompany its deceased owner into the afterlife.\n"
  },
  {
    "file": "knowledge/concepts/concept-granitic-orthostat-chamber-and-capstone-cist-burial-mechanics.md",
    "slug": "concept-granitic-orthostat-chamber-and-capstone-cist-burial-mechanics",
    "category": "concept",
    "name_en": "Granitic Orthostat Slabs, Port-Hole Passage Alignment & Capstone Megalithic Cist Architecture",
    "name_ta": "செங்குத்துப் பலகைக் கற்கள், வட்டத் துளை வாயில் மற்றும் பெருங்கல் மூடுபாறைப் பொருத்து",
    "era": "Iron Age to Sangam Era",
    "year_start": -800,
    "year_end": 100,
    "thinai": "kurinji",
    "summary_en": "The monumental megalithic architecture of dolmenoid cists enclosing terracotta sarcophagi: four dressed granite orthostats set in a clockwise swastika plan to resist lateral earth pressure, pierced by an eastern circular port-hole, and capped by multi-ton granitic slabs levered on earth ramps.",
    "summary_ta": "சுடுமண் ஈமப்பேழைகளைப் பாதுகாக்கும் கருங்கல் திட்டைக் கட்டுமானம்: சுழல்முறைப் பொருத்தில் நடப்பட்ட நான்கு செங்குத்துப் பலகைக் கற்கள், கிழக்கு நோக்கிய வட்டத் துளை வாயில், மற்றும் மண் சாய்வுப் பாதைகளில் உருட்டி ஏற்றப்பட்ட பல டன் எடையுள்ள மூடுபாறைகளின் பொறியியல்.",
    "sources": [
      "Sundara: The Early Chamber Tombs of South India",
      "Childe: Megaliths",
      "Rajan: Archaeological Gazetteer of Tamil Nadu"
    ],
    "content": "---\nid: concept-granitic-orthostat-chamber-and-capstone-cist-burial-mechanics\ntitle: Granitic Orthostat Slabs, Port-Hole Passage Alignment & Capstone Megalithic Cist Architecture\ntype: concept\nera: Iron Age to Sangam Era (c. 800 BCE - 100 CE)\nthinai: kurinji (Megalithic Structural Engineering)\nstatus: canonical\n---\n\n# Granitic Orthostat Slabs, Port-Hole Passage Alignment & Capstone Megalithic Cist Architecture\n\n## 1. Architectural Layout & Swastika Plan\nTo construct a protective subterranean or semi-subterranean vault (*Kallara / Cist*) for a terracotta sarcophagus, ancient Tamil megalith builders utilized a sophisticated interlocking structural plan:\n- **Orthostat Arrangement**: Four monolithic granitic slabs (each 2 to 3 meters long, 0.2 to 0.3 meters thick) were erected vertically in a clockwise **swastika configuration**, where each slab extends beyond the edge of the adjacent orthostat.\n- **Lateral Earth Pressure Resistance**: This interlocking geometry prevented the stone walls from collapsing inward under the immense hydrostatic and lateral pressure of the surrounding cairn rubble pack ($P = \\gamma \\cdot h \\cdot K_0$).\n\n## 2. Port-Hole Engineering (*Aan-Thulai / Korangupattadai*)\nThe eastern orthostat was systematically pierced with a circular or U-shaped aperture measuring 30 to 45 cm in diameter:\n- **Acoustic and Soul Conduit**: Believed to serve as a spiritual portal through which the spirit of the deceased could exit, and through which secondary offerings of milk, grain, and oil could be introduced by descendants.\n- **Port-Hole Plugs**: The opening was sealed with a fitted thin granite shutter slab.\n\n## 3. Capstone Levering Mechanics\nThe entire chamber was roofed by a colossal unhewn granitic capstone weighing between 5 and 25 metric tons:\n1. **Incline Ramp Building**: A tamped earth and gravel ramp was erected to the height of the orthostats.\n2. **Timber Rollers & Levering**: Levers of hardwood (*Vengai*) and timber rollers moved the stone upward until it rested flush upon the upright stone edges.\n"
  },
  {
    "file": "knowledge/characters/char-paiyampalli-master-sarcophagus-potter-kavikkal-kuyavan.md",
    "slug": "char-paiyampalli-master-sarcophagus-potter-kavikkal-kuyavan",
    "category": "character",
    "name_en": "Master Megalithic Sarcophagus Sculptor & Kiln Potter: Kavikkal Kuyavan of Paiyampalli",
    "name_ta": "பையம்பள்ளி பெருங்கற்கால ஈமப்பேழைச் சுடுமண் சிற்பக் குயவன்",
    "era": "Iron Age to Sangam Era",
    "year_start": -800,
    "year_end": -600,
    "thinai": "kurinji",
    "summary_en": "The hereditary master potter and pyrotechnologist of the Palar valley who engineered massive multi-legged terracotta sarcophagi, zoomorphic ram-headed lids, and high-fired grave pottery for clan chieftains.",
    "summary_ta": "பையம்பள்ளி மற்றும் பாலாற்றுப் படுகையின் வேளிர்களுக்குத் தேவையான பல்கால் சுடுமண் ஈமப்பேழைகள், விலங்குருவ மூடிகள் மற்றும் ஈம மட்பாண்டங்களைத் தீப்பிழம்பில் சுட்டெடுத்த தலைசிறந்த குயவர் தலைவர்.",
    "sources": [
      "Paiyampalli Excavation Reports",
      "Rajan: Situating Megalithic Craft Specialists"
    ],
    "content": "---\nid: char-paiyampalli-master-sarcophagus-potter-kavikkal-kuyavan\ntitle: Master Megalithic Sarcophagus Sculptor & Kiln Potter: Kavikkal Kuyavan of Paiyampalli\ntype: character\nera: Iron Age to Sangam Era (c. 800 - 600 BCE)\nthinai: kurinji (Protohistoric Ceramic Pyrotechnics)\nstatus: canonical\n---\n\n# Master Megalithic Sarcophagus Sculptor & Kiln Potter: Kavikkal Kuyavan of Paiyampalli\n\n## 1. Professional Status & Sacred Function\nThe **Kavikkal Kuyavan** (master sarcophagus potter) held a sacred, ritualized position at the nexus of technology and death. Far beyond ordinary utilitarian kitchenware manufacture, crafting a monumental 100 kg burial sarcophagus required specialized knowledge of clay mechanics, temper selection, and prolonged pit firing.\n\n## 2. Technical Specializations\n- **Grog & Temper Formulations**: Mixing precise ratios of calcined grog and fine river gravel to absorb shrinkage stresses and prevent body cracks during drying.\n- **Hollow Leg Welding**: Perfecting the luting of wheel-thrown conical legs onto the wet hand-built trough, inserting breath vents to equalize pressure.\n- **Zoomorphic Modeling**: Hand-sculpting the iconic ram and bull terminals that served as totemic clan emblems.\n\n## 3. Social Legacy\nHis workshops supplied the necropolises across the Javadi hill fringes, establishing the ceramic baseline that evolved into the monumental terracotta sculpture traditions of classical Tamil Nadu.\n"
  },
  {
    "file": "knowledge/characters/char-sanur-megalithic-chamber-builder-kallaraignar.md",
    "slug": "char-sanur-megalithic-chamber-builder-kallaraignar",
    "category": "character",
    "name_en": "Master Megalithic Orthostat Architect & Capstone Leverer: Sanur Kallaraignar",
    "name_ta": "சானூர்ப் பெருங்கல் அறை மற்றும் மூடுபாறை அமைக்கும் சிற்பி",
    "era": "Iron Age to Sangam Era",
    "year_start": -600,
    "year_end": -400,
    "thinai": "mullai",
    "summary_en": "The veteran Megalithic architect and stone engineer who organized clan labor to quarry monolithic granite orthostats, peck out circular port-hole apertures, and hoist massive multi-ton capstones over subterranean sarcophagus chambers.",
    "summary_ta": "சானூர் பெருங்கற்காலக் களத்தில் பாறைகளைப் பிளந்து பலகைக் கற்களை நட்டு, வட்டத் துளை வாயில்களைச் செதுக்கி, பல டன் எடையுள்ள மூடுபாறைகளை ஏற்றி ஈம அறைகளை நிறுவிய பெருங்கல் கட்டடக் கலைஞர்.",
    "sources": [
      "Sanur Megalithic Excavations (Ancient India 15)",
      "Megalithic Architecture in Tamil Nadu"
    ],
    "content": "---\nid: char-sanur-megalithic-chamber-builder-kallaraignar\ntitle: Master Megalithic Orthostat Architect & Capstone Leverer: Sanur Kallaraignar\ntype: character\nera: Iron Age to Sangam Era (c. 600 - 400 BCE)\nthinai: mullai (Megalithic Stone Engineering)\nstatus: canonical\n---\n\n# Master Megalithic Orthostat Architect & Capstone Leverer: Sanur Kallaraignar\n\n## 1. The Craft of the Kallaraignar\nThe **Kallaraignar** (chamber stone-mason) was the master engineer responsible for designing and raising the Megalithic stone monuments (*Kalkudai / Korangupattadai*) that dotted the pasturelands of northern Tamilakam.\n\n## 2. Engineering Operations\n1. **Quarry Cleaving**: Selecting natural sheet-granite outcrops and driving wooden wedges along foliation planes to split out broad, uniform orthostats.\n2. **Port-Hole Pecking**: Utilizing heavy dolerite hammerstones to peck out an exact 35 cm circular entrance through 20 cm thick granite.\n3. **Capstone Raising**: Organizing dozens of clan men and draught oxen using timber sledges and inclined earth ramps to position 15-ton capstones directly atop the vertical walls without disturbing the delicate terracotta sarcophagus inside.\n"
  },
  {
    "file": "knowledge/places/place-paiyampalli-megalithic-sarcophagus-haven.md",
    "slug": "place-paiyampalli-megalithic-sarcophagus-haven",
    "category": "place",
    "name_en": "Paiyampalli: Ancient Megalithic Terracotta Sarcophagi & Iron Metallurgy Haven",
    "name_ta": "பையம்பள்ளி - பண்டைய பெருங்கற்கால ஈமப்பேழை மற்றும் இரும்புத் தொழிற்பட்டறைத் தளம்",
    "era": "Iron Age to Sangam Era",
    "year_start": -1000,
    "year_end": 300,
    "thinai": "kurinji",
    "summary_en": "Landmark archaeological type-site in the Palar valley of northern Tamil Nadu excavated by the ASI, celebrated for unearthing multi-legged terracotta sarcophagi, iron smelting furnaces, socketed iron weaponry, and continuous habitation from the Neolithic to the Megalithic era.",
    "summary_ta": "வட தமிழகத்தில் பாலாற்றுப் படுகையில் அமைந்துள்ள உலகப் புகழ்பெற்ற தொல்லியல் தளம்; பல்கால் சுடுமண் ஈமப்பேழைகள், இரும்பு உருக்கு ஆலைகள் மற்றும் கி.மு. 1000 காலத்திய தொடர் வரலாற்று வாழ்விடச் சான்றுகளைக் கொண்ட தளம்.",
    "sources": [
      "ASI Excavation Memoir: Paiyampalli",
      "Indian Archaeology: A Review",
      "Rao: Protohistoric Chronology of South India"
    ],
    "content": "---\nid: place-paiyampalli-megalithic-sarcophagus-haven\ntitle: Paiyampalli: Ancient Megalithic Terracotta Sarcophagi & Iron Metallurgy Haven\ntype: place\nera: Iron Age to Sangam Era (c. 1000 BCE - 300 CE)\nthinai: kurinji (Megalithic Archaeology & Metallurgy)\nstatus: canonical\n---\n\n# Paiyampalli: Ancient Megalithic Terracotta Sarcophagi & Iron Metallurgy Haven\n\n## 1. Topography & Environmental Setting\n**Paiyampalli** (lat 12.5000° N, lng 78.5000° E) lies in the Tirupattur taluk of northern Tamil Nadu, situated between two granite hillocks overlooking fertile alluvial terraces fed by the upper tributaries of the Palar river. \n\nThe site provided immediate access to high-grade magnetite iron ore from the adjacent hill ranges, abundant quartz sands, and dense deciduous forests (*Kurinji-Mullai*) for charcoal fueling.\n\n## 2. Archaeological Significance\nExcavations under S.R. Rao revealed a stratified succession:\n- **Neolithic Phase (c. 1400–1000 BCE)**: Pit dwellings, polished stone tools, primitive burnished grey pottery.\n- **Iron Age Megalithic Phase (c. 1000–300 BCE)**: Introduction of bloomery iron smelting, wheel-thrown Black-and-Red Ware, and monumental burial grounds featuring **legged terracotta sarcophagi** entombed within stone-circle cists.\n\n## 3. Cultural Synthesis\nPaiyampalli proved conclusively that northern Tamil Nadu was an active metallurgical cradle where pyrotechnology, monumental funerary ceramics, and advanced granite cist architecture developed in continuous sequence long before early historic urbanism.\n"
  }
]
EDGES = [
  [
    "text-manimekalai-funerary-burial-types-and-sarcophagi-poetry",
    "describes_burial_in",
    "concept-multi-legged-terracotta-sarcophagus-molding-and-firing-kavikkal",
    "cultural",
    "Post-Sangam Classical Era",
    "Manimekalai cataloguing five classical burial practices including sarcophagi",
    "Manimekalai 6:64-70"
  ],
  [
    "insc-paiyampalli-megalithic-burial-complex-epigraphs",
    "documents_excavations_at",
    "place-paiyampalli-megalithic-sarcophagus-haven",
    "archaeological",
    "Iron Age to Sangam Era",
    "Excavations unearthing multi-legged sarcophagi and iron weapons",
    "IAR 1964-68"
  ],
  [
    "insc-sanur-megalithic-sarcophagus-and-dolmenoid-cist-charters",
    "records_legged_coffins_in",
    "concept-granitic-orthostat-chamber-and-capstone-cist-burial-mechanics",
    "archaeological",
    "Iron Age to Sangam Era",
    "Dolmenoid cists enclosing terracotta sarcophagi at Sanur",
    "Ancient India No. 15"
  ],
  [
    "concept-multi-legged-terracotta-sarcophagus-molding-and-firing-kavikkal",
    "fitted_with_sculptured_lid",
    "concept-zoomorphic-ram-and-elephant-funerary-lid-sculpture",
    "technological",
    "Iron Age to Sangam Era",
    "Terracotta sarcophagi fitted with zoomorphic ram and elephant lids",
    "Rea 1915"
  ],
  [
    "concept-multi-legged-terracotta-sarcophagus-molding-and-firing-kavikkal",
    "entombed_within_orthostat_cist",
    "concept-granitic-orthostat-chamber-and-capstone-cist-burial-mechanics",
    "architectural",
    "Iron Age to Sangam Era",
    "Subterranean granitic orthostat chambers protecting terracotta coffins",
    "Sundara 1975"
  ],
  [
    "concept-black-and-red-ware-funerary-vessels-and-iron-weapon-offerings",
    "deposited_inside_sarcophagus",
    "concept-multi-legged-terracotta-sarcophagus-molding-and-firing-kavikkal",
    "archaeological",
    "Iron Age to Sangam Era",
    "BRW bowls and socketed iron axes placed beside skeletal remains",
    "Ancient India 15"
  ],
  [
    "char-paiyampalli-master-sarcophagus-potter-kavikkal-kuyavan",
    "sculpted_terracotta_coffins_at",
    "place-paiyampalli-megalithic-sarcophagus-haven",
    "social",
    "Iron Age to Sangam Era",
    "Master protohistoric potter engineering monumental burial sarcophagi",
    "Paiyampalli Memoir"
  ],
  [
    "char-sanur-megalithic-chamber-builder-kallaraignar",
    "levered_capstones_over",
    "concept-granitic-orthostat-chamber-and-capstone-cist-burial-mechanics",
    "architectural",
    "Iron Age to Sangam Era",
    "Quarrying orthostats and positioning multi-ton capstones over cists",
    "Sanur Excavation"
  ],
  [
    "char-paiyampalli-master-sarcophagus-potter-kavikkal-kuyavan",
    "molded_zoomorphic_lids",
    "concept-zoomorphic-ram-and-elephant-funerary-lid-sculpture",
    "artistic",
    "Iron Age to Sangam Era",
    "Hand-modeling horned ram and elephant lid terminals",
    "Megalithic Ceramic Art"
  ],
  [
    "place-paiyampalli-megalithic-sarcophagus-haven",
    "yielded_iron_deposits_described_in",
    "concept-black-and-red-ware-funerary-vessels-and-iron-weapon-offerings",
    "archaeological",
    "Iron Age to Sangam Era",
    "Stratified excavation levels yielding pristine socketed iron implements",
    "IAR 1967-68"
  ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 20 Corpus 2: Megalithic Sarcophagi & Iron Deposits into Moolam Chronicles & Life Graph...")
    os.makedirs(MOOLAM_KNOWLEDGE, exist_ok=True)

    # Phase 1: Write Markdown Files
    print("\n[Phase 1] Writing 10 Markdown Knowledge Dossiers...")
    for d in DOSSIERS:
        full_path = os.path.join("/mnt/h/DevTools/Projects/learn-ai/moolam-chronicles", d["file"])
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
            json.dumps({"category": d["category"], "canonical_file": d["file"]}),
            d["sources"]
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
                f"shelf-{d['category']}",
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

    print(f"\n🎉 Batch 20 Corpus 2: Megalithic Sarcophagi & Iron Deposits Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
