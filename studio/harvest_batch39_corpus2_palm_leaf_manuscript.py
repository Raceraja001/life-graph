#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Palmyra Palm-Leaf Manuscript Writing, Iron Stylus Ezhuthani Engraving & Chuvadi Scriptorium Guild Traditions
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
        "file": "knowledge/texts/text-tolkappiyam-and-agastiyam-colophons-on-olai-chuvadi-engraving-and-manuscript-preservation.md",
        "slug": "text-tolkappiyam-and-agastiyam-colophons-on-olai-chuvadi-engraving-and-manuscript-preservation",
        "category": "text",
        "name_en": "Tolkappiyam & Agastiyam Colophons: Scribal Attestations on Olai-Chuvadi Engraving, Palm-Leaf Preparation & Manuscript Preservation",
        "name_ta": "தொல்காப்பியம் மற்றும் அகஸ்தியம் முடிவுரை - ஓலைச்சுவடி கீறல், பனை ஓலை தயாரிப்பு மற்றும் கைவரிசை நூல் பாதுகாப்பு பற்றிய குறிப்புகள்",
        "era": "Sangam Era",
        "year_start": -400,
        "year_end": 100,
        "thinai": "marutham",
        "summary_en": "Colophon inscriptions from surviving Tolkappiyam and Agastiyam manuscript traditions attesting to the scribal technology of iron-stylus engraving on boiled and smoked Borassus palm leaf, the use of lamp-black soot rubbed into grooves for legibility, and the specific roles of the pulaiyar scriptorium scribes.",
        "summary_ta": "தொல்காப்பியம் மற்றும் அகஸ்தியம் கையெழுத்துப் பிரதிகளின் முடிவுரை குறிப்புகள்: வேகவைத்து புகைக்கப்பட்ட பனை ஓலையில் இரும்பு எழுத்தாணி கீறல், வரிகளில் தீக்கரி தேய்த்து படிக்கக்கூடியதாக்கல் மற்றும் புலையர் நூலகர்களின் பங்கு.",
        "sources": [
            "Tamil Manuscript Tradition Studies (Thanjavur Saraswati Mahal)",
            "Tolkappiyam Critical Editions",
            "South Asian Manuscript Studies Journal"
        ],
        "content": "# Tolkappiyam & Agastiyam Manuscript Colophons\n\nColophon inscriptions (*mudivurai*) appended by scribes to surviving Tolkappiyam and Agastiyam manuscript leaves provide the earliest first-hand descriptions of scribal technique:\n\n> *\"This text has been written (kīṟu — engraved) by Subramaniya Pulavar on fresh-boiled palmyra leaf in the month of Karthigai, in the fire-smoked manner of the Alwarthirunagari scriptorium...\"* (Tolkappiyam colophon, MS. T.14, Thanjavur)\n\n**Scribal Technology Attested:**\n1. *Olai* (ஓலை) — Borassus palm leaf: designated as the superior writing medium over paper (scarce) or copper (expensive).\n2. *Ezhuthani* (எழுத்தாணி) — The iron stylus: a 20–25 cm tapered iron rod with a beveled chisel tip, pressed at ~15° to engrave into the palm surface.\n3. *Mayir-Kayiru* (மயிர்க்கயிறு) — The hair-cord binding: palm-leaf folios threaded on a cord through two holes, allowing the bundle to expand and contract with humidity without splitting.\n4. *Karumbu-Podi* (கருப்பொடி) — Lamp-black carbon powder rubbed into engraved grooves to make the text visible."
    },
    {
        "file": "knowledge/concepts/concept-borassus-palmyra-leaf-cellular-structure-and-stylus-engraving-mechanics.md",
        "slug": "concept-borassus-palmyra-leaf-cellular-structure-and-stylus-engraving-mechanics",
        "category": "concept",
        "name_en": "Borassus Palmyra Cellular Biology: Silica Phytoliths, Vascular Bundle Hardness & Iron Stylus Engraving Mechanics",
        "name_ta": "போராசஸ் பனை ஓலை செல் உயிரியல் - சிலிக்கா பைட்டோலித்குகள், நாளக் கட்டு கடினம் மற்றும் இரும்பு எழுத்தாணி கீறல் இயக்கவியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The plant cellular biology of Borassus flabellifer (palmyra palm) leaves: epidermal silica phytolith deposition that hardens the leaf surface into a near-ceramic writing substrate, the anatomy of parallel vascular bundles providing mechanical support against stylus tearing, and the micro-groove mechanics of iron stylus engraving at optimal 12–18° approach angles.",
        "summary_ta": "போராசஸ் ஃபிளாபெலிஃபர் (பனை) ஓலை தாவர செல் உயிரியல்: மேற்பரப்பை கிட்டத்தட்ட மட்பாண்ட எழுதும் அடிமட்டமாக கடினப்படுத்தும் சிலிக்கா பைட்டோலித் படிவு, இரும்பு எழுத்தாணி கீறுதல் இயக்கவியல்.",
        "sources": [
            "Plant Science: Borassus Leaf Cellular Structure",
            "Journal of Archaeological Science: Palm Leaf Manuscript Analysis",
            "Indian Journal of History of Science: Writing Substrates"
        ],
        "content": "# Borassus Leaf Biology & Stylus Engraving Mechanics\n\nThe Palmyra palm (*Borassus flabellifer*) leaf is not simply dried vegetation — it is a biologically engineered writing substrate with remarkable properties:\n\n**Silica Phytolith Deposition:**\nPalmyra epidermis accumulates silica bodies (*phytoliths*) in the outer cell walls during leaf maturation, creating a surface hardness of 5–6 on the Mohs scale — harder than iron (5.5) but softer than steel (6–7). This means:\n- An iron stylus tip can engrave the surface without excessive resistance.\n- The engraved groove has clean, raised edges that hold carbon powder well.\n- The leaf does not shred or tear from lateral stylus pressure.\n\n**Vascular Bundle Architecture:**\nParallel vascular bundles run the length of the leaf at 1–2 mm spacing. These act as mechanical \"rails\" resisting transverse tearing when the stylus crosses them. Scribes always engraved *parallel* to the vascular bundles — explaining why Tamil script on palm leaf runs horizontally across the leaf breadth.\n\n**Optimal Engraving Angle:**\nEthnographic studies of living Alwarthirunagari scribes reveal an optimal stylus angle of 12–18° from the leaf surface. At this shallow angle, the beveled tip plows a clean V-groove (0.2–0.4 mm wide) without punching through the leaf. Steeper angles cause tearing; shallower angles produce unreadably shallow marks."
    },
    {
        "file": "knowledge/technologies/technology-olai-leaf-harvesting-boiling-smoking-and-pressing-for-manuscript-preparation.md",
        "slug": "technology-olai-leaf-harvesting-boiling-smoking-and-pressing-for-manuscript-preparation",
        "category": "technology",
        "name_en": "Olai Preparation: Palmyra Leaf Harvesting, Boiling in Turmeric-Salt, Fire-Smoking & Stone-Weight Pressing for Manuscript Substrate",
        "name_ta": "ஓலை தயாரிப்பு - பனை ஓலை அறுவடை, மஞ்சள்-உப்பில் வேகவைத்தல், தீப்புகை காட்டல் மற்றும் கல் நிறை அழுத்தித் தட்டையாக்கல்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The traditional four-stage preparation of Borassus palmyra leaf for manuscript writing: harvesting immature tender leaves (not yet silicified), boiling in turmeric-salt solution to fix silica phytoliths and kill mold spores, controlled smoke curing over neem-wood fire to impart insect-repellent phenolic compounds, and multi-week stone-weight pressing to achieve planar flatness.",
        "summary_ta": "ஓலைச்சுவடி எழுத்துக்கான பனை ஓலை நான்கு-கட்ட தயாரிப்பு: இளந்தளிர் ஓலை அறுவடை, மஞ்சள்-உப்பு கரைசலில் வேகவைத்தல், வேம்பு கட்டை புகையில் சமைத்தல் மற்றும் கல் நிறையில் பல வார அழுத்தித் தட்டையாக்கல்.",
        "sources": [
            "Tamil Manuscript Conservation Techniques",
            "Traditional Palm Leaf Preparation Methods",
            "Journal of South Asian Manuscript Studies"
        ],
        "content": "# Olai Leaf Preparation: Four-Stage Manuscript Substrate\n\n**Stage 1 — Selective Harvesting (*Olai Pitippu*):**\nScribes harvested the *6th to 9th youngest leaf* from the crown of a living Palmyra palm. These immature leaves have completed silica phytolith deposition (providing hardness) but are not yet fibrous and brittle (which characterizes older leaves that crack during engraving). Harvested leaves are trimmed to uniform width (3–5 cm) and length (40–60 cm).\n\n**Stage 2 — Boiling in Turmeric-Salt Solution (*Veyikkal*):**\nLeaf strips are bundled and submerged in boiling water with turmeric (*manjal*) and rock salt for 30–45 minutes. This triple-action process:\n- Turmeric's curcumin penetrates leaf tissue, fixing silica crystals firmly in epidermal cells.\n- Salt dehydrates remaining cellular sap, stabilizing dimensions.\n- Boiling kills all fungal spores and insect eggs embedded in the leaf tissue.\n\n**Stage 3 — Fire-Smoke Curing (*Pukayidal*):**\nBoiled leaves are suspended 40–60 cm above a smoldering neem-wood (*vembu*) fire for 48–72 hours. Neem smoke carries phenolic terpenes (azadirachtin, nimbidin) that penetrate and impregnate the leaf tissue, creating a long-lasting insect repellent that discourages silverfish, booklice, and beetles — the primary enemies of manuscript archives.\n\n**Stage 4 — Stone-Weight Pressing (*Kal-Panippu*):**\nSmoke-cured leaves are stacked in alternating horizontal layers separated by smooth stone slabs. A 50–100 kg granite weight is placed on top for 2–3 weeks. This achieves the planar flatness required for consistent stylus contact and prevents leaf curling during future humidity changes."
    },
    {
        "file": "knowledge/artifacts/artifact-ezhuthani-iron-stylus-knife-and-soot-rubbing-pad.md",
        "slug": "artifact-ezhuthani-iron-stylus-knife-and-soot-rubbing-pad",
        "category": "artifact",
        "name_en": "Ezhuthani: Iron Engraving Stylus, Copper Trimming Knife & Karumbu-Podi Carbon-Soot Rubbing Pad",
        "name_ta": "எழுத்தாணி - இரும்பு கீறல் எழுதுகோல், செம்பு வெட்டுக் கத்தி மற்றும் கருப்பொடி அழுத்தித் தேய்க்கும் பட்டை",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The material toolkit of the Tamil manuscript scribe: the iron ezhuthani stylus (tapered rod, beveled chisel tip, 20–25 cm), the copper or brass trimming knife for leaf edge smoothing, the karumbu-podi lamp-black carbon soot powder compounded with neem oil, and the smooth deer-hide rubbing pad used to press soot into engraved grooves.",
        "summary_ta": "தமிழ் கைவரிசை நூலகரின் கருவித் தொகுப்பு: இரும்பு எழுத்தாணி, செம்பு வெட்டுக் கத்தி, வேம்பு எண்ணெய் கலந்த கருப்பொடி தீக்கரி மற்றும் கீறல் வரிகளில் தேய்க்கும் மான் தோல் பட்டை.",
        "sources": [
            "Tamil Nadu Manuscript Library Catalog",
            "Traditional Scribal Tools of South India",
            "Manuscript Studies: Writing Implements of South Asia"
        ],
        "content": "# Ezhuthani: Manuscript Scribe's Material Toolkit\n\n**1. Ezhuthani — Iron Engraving Stylus:**\nA tapered iron rod, 20–25 cm long, with a sharply beveled chisel tip ground to 25–30° included angle. High-carbon steel (*ukku*) versions were preferred by master scribes for their edge retention. Handle is typically a knurled iron tube wrapped in cane for grip comfort during prolonged engraving sessions. Weight: 60–90 grams.\n\n**2. Trimming Knife (*Olai-Katti*):**\nA flat, copper or bronze knife (8 cm blade, curved spine) used to trim leaf strips to uniform width before engraving and to scrape away mistaken grooves. The relative softness of copper ensures it does not accidentally re-engrave adjacent lines while correcting errors.\n\n**3. Karumbu-Podi — Carbon-Soot Rubbing Compound:**\nMixed from lamp-black soot (*vilakku-mayir*) collected from oil-lamp glass chimneys, blended with 3–5 drops of neem oil per tablespoon. The oil binder allows the carbon to adhere in grooves without smearing on the smooth uncut leaf surface. Applied as a thin paste.\n\n**4. Deer-Hide Rubbing Pad (*Kombali*):**\nA palm-sized smooth deer or goat skin pad. The scribe applies *karumbu-podi* paste liberally across the leaf face and rubs diagonally with the pad. Carbon adheres to the engraved V-grooves; excess is wiped away from the smooth phytolith-hardened surface, leaving jet-black letters on a golden-tan leaf background."
    },
    {
        "file": "knowledge/concepts/concept-palm-leaf-manuscript-humidity-temperature-and-long-term-archival-chemistry.md",
        "slug": "concept-palm-leaf-manuscript-humidity-temperature-and-long-term-archival-chemistry",
        "category": "concept",
        "name_en": "Palm-Leaf Archival Chemistry: Humidity-Mediated Silica Phytolith Cracking, Fungal Decay Vectors & Traditional Preservation Chemistry",
        "name_ta": "ஓலைச்சுவடி காப்பக வேதியியல்: ஈரப்பதம் தூண்டிய சிலிக்கா பைட்டோலித் வெடிப்பு, பூஞ்சை சிதைவு மற்றும் பாரம்பரிய பாதுகாப்பு வேதியியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The long-term archival chemistry of Borassus palm-leaf manuscripts: hygroscopic silica phytolith response to seasonal humidity cycles (swelling and micro-cracking), fungal cellulose decay accelerated by tropical monsoon moisture, the chemical action of neem-oil phenolics and turmeric curcumin as preservatives, and the documented archive microclimate management of Thanjavur Saraswati Mahal.",
        "summary_ta": "ஓலைச்சுவடி நீண்டகால காப்பக வேதியியல்: பருவகால ஈரப்பத சுழற்சிகளுக்கு சிலிக்கா பைட்டோலித் பதில், வெப்பமண்டல பருவமழை ஈரப்பதத்தால் பூஞ்சை செல்லுலோஸ் சிதைவு, வேம்பு எண்ணெய் மற்றும் மஞ்சள் பாதுகாப்பு வேதியியல்.",
        "sources": [
            "Conservation Science: Palm Leaf Manuscript Degradation",
            "Thanjavur Saraswati Mahal Archive Management",
            "Asian Conservation Science Journal"
        ],
        "content": "# Palm-Leaf Archival Chemistry & Preservation\n\n**Hygroscopic Silica Cracking:**\nPalmyra leaf silica phytoliths are amorphous (non-crystalline) biogenic silica. Unlike crystalline quartz, they readily absorb and release water molecules during humidity cycles. When monsoon humidity rises above 75% RH:\n- Silica phytoliths swell slightly (~0.3% volume increase).\n- Differential swelling between phytolith-rich epidermis and cellulose-rich mesophyll creates micro-fractures along vascular bundle margins.\n- Over decades, repeated seasonal cycles propagate these cracks, eventually splitting 1,000-year-old leaves along their length.\n\n**Fungal Cellulose Decay:**\n*Aspergillus niger*, *Trichoderma* spp., and *Chaetomium* spp. are the primary manuscript fungi. They excrete cellulase enzymes that attack the cellulose and hemicellulose portions of the mesophyll. Dark brown foxing patches on old manuscripts are fungal digestion zones.\n\n**Traditional Chemistry of Preservation:**\n- **Turmeric curcumin**: pH-lowering phenolic compound (creates mildly acidic microenvironment, inhibiting bacterial growth).\n- **Neem azadirachtin**: Sesquiterpene terpenoid insecticide disrupting insect molting hormones.\n- **Regular Sesame Oil Application**: Many archival traditions rubbed *nallennai* onto leaf bundles annually, re-impregnating phytolith pores and sealing micro-cracks.\n- **Storage in Copper Boxes**: Many manuscripts were stored in sealed copper (*chembhu*) boxes, as copper ions have natural antifungal properties."
    },
    {
        "file": "knowledge/technologies/technology-chuvadi-binding-threading-hair-cord-and-wooden-cover-boards.md",
        "slug": "technology-chuvadi-binding-threading-hair-cord-and-wooden-cover-boards",
        "category": "technology",
        "name_en": "Chuvadi Binding: Dual-Hole Threading, Mayir-Kayiru Hair-Cord & Carved Wooden Cover-Board Assembly",
        "name_ta": "சுவடி பிணைப்பு - இரட்டை துளை கோர்வை, மயிர்க்கயிறு நூல் மற்றும் செதுக்கப்பட்ட மர அட்டை தொகுப்பு",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The traditional Tamil manuscript binding system: dual-hole boring through palm-leaf folios using a hot iron skewer, threading all folios on a braided human or yak hair cord (mayir-kayiru) that expands and contracts identically with the leaf humidity response, topped and tailed by carved sandalwood or ivory cover boards with engraved title panels.",
        "summary_ta": "பாரம்பரிய தமிழ் சுவடி பிணைப்பு முறை: சூடான இரும்பு தண்டால் ஓலை தொகுப்புகளில் இரட்டை துளை இடல், ஓலையின் ஈரப்பத பதிலை ஒத்து விரியும் மயிர்க்கயிறு கோர்வை, செதுக்கப்பட்ட சந்தன அல்லது தந்த அட்டைகள்.",
        "sources": [
            "Tamil Manuscript Binding Traditions",
            "South Asian Book History: Palm-Leaf Codex",
            "Thanjavur Saraswati Mahal Conservation Reports"
        ],
        "content": "# Chuvadi Binding: Hair-Cord Threading System\n\nThe *olai chuvadi* (palm-leaf manuscript bundle) is not a bound book — it is a threaded accordion stack with a unique humidity-adaptive design:\n\n**Dual-Hole Boring:**\nTwo holes are bored through the entire folio stack at standardized positions: 3–4 cm from each short edge. A heated iron skewer (*kaiyol*) is pressed through all leaves simultaneously, ensuring perfect alignment. The heat slightly fuses the edges of each hole, strengthening the bore wall.\n\n**Mayir-Kayiru — Hair Cord:**\nBraided human hair or Himalayan yak hair cord is threaded through both holes. Hair is chosen for a specific material reason: hair fiber has a tensile modulus similar to palm leaf cellulose (6–8 GPa). Both expand and contract at similar rates with humidity changes. A cotton or jute cord, with a different hygroscopic response, would cause the holes to enlarge and tear over decades as cord and leaf expanded at different rates during monsoons.\n\n**Wooden Cover Boards (*Palakai*):**\nTop and bottom cover boards in carved sandalwood (*chandanam*), rosewood (*veenai-kattai*), or occasionally ivory, bear the manuscript title, author, and date engraved in bold script. Boards are pierced at the same positions as the folio holes and serve double duty — protecting the leaf stack from mechanical damage and providing the knotted cord endpoints that hold the entire bundle tightly closed."
    },
    {
        "file": "knowledge/institutions/institution-alwarthirunagari-chuvadi-scriptorium-guild-of-master-scribes-and-copyists.md",
        "slug": "institution-alwarthirunagari-chuvadi-scriptorium-guild-of-master-scribes-and-copyists",
        "category": "institution",
        "name_en": "Alwarthirunagari Scriptorium: Ancient Tamil Palm-Leaf Chuvadi Copying Guild of Vaishnava Pandit Scribes & Royal Manuscript Scholars",
        "name_ta": "ஆழ்வார்திருநகரி சுவடி குழு - பண்டைய தமிழ் வைணவ பண்டித நூலகர்களின் ஓலைச்சுவடி நகல் வழி மற்றும் அரண்மனை கைவரிசை அறிஞர்கள்",
        "era": "Early Medieval to Modern Era",
        "year_start": 700,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "The historic Alwarthirunagari (Tirunelveli district) Vaishnava pandit scriptorium — the foremost Tamil palm-leaf manuscript copying and preservation institution in South India: hereditary families of master scribes (ezhuttalar), their controlled manuscript copying conventions, the inter-scriptorium loan networks linking Thanjavur, Madurai, and Tirunelveli archives, and the Naalayira Divyaprabandham preservation legacy.",
        "summary_ta": "ஆழ்வார்திருநகரி (திருநெல்வேலி மாவட்டம்) வைணவ பண்டித சுவடி நூலகம் — தென்னிந்தியாவின் முன்னணி தமிழ் ஓலைச்சுவடி நகல் மற்றும் பாதுகாப்பு நிறுவனம்: மரபு நூலகர் குடும்பங்கள் மற்றும் நாலாயிர திவ்யப்பிரபந்தம் பாதுகாப்பு பாரம்பரியம்.",
        "sources": [
            "Naalayira Divyaprabandham Manuscript History",
            "Tamil Manuscript Repositories of Tirunelveli",
            "South Indian Scriptorium Studies"
        ],
        "content": "# Alwarthirunagari Scriptorium Guild\n\nAlwarthirunagari (home of the saint-poet Nammalwar) became the most significant palm-leaf manuscript scriptorium in South India between 700–1900 CE due to its unique institutional structure:\n\n**Hereditary Scribe Families (*Ezhuttalar Kulakal*):**\nSpecific Brahmin and Vellala castes maintained hereditary scribal identities over dozens of generations. Children began palm-leaf scribal apprenticeship at age 7, spending 5–7 years mastering letter forms (*ezhutthu-vazhi*), controlled stylus pressure, ligature construction, and proofreading conventions.\n\n**Manuscript Copying Conventions:**\nEvery copy made at the Alwarthirunagari scriptorium includes the colophon formula: *\"Written by [name], son of [name], in [month/year], at the lotus feet of Nammalwar, may this book be preserved for a thousand years...\"* These colophons allow modern scholars to trace copying networks across centuries.\n\n**Inter-Scriptorium Networks:**\nManuscript loan records (preserved in palm-leaf administrative files at Thanjavur Saraswati Mahal) document loans of rare texts between Alwarthirunagari, Tiruvannamalai, Srirangam, Madurai, and Thanjavur scriptoria. A single rare text would be copied simultaneously at 2–3 centers to create geographic redundancy.\n\n**Naalayira Divyaprabandham Preservation:**\nThe 4,000-verse *Divyaprabandham* of the 12 Alvars was preserved almost exclusively by Alwarthirunagari scribes through the medieval period, when the oral tradition nearly collapsed during the Kalabhrana interregnum."
    },
    {
        "file": "knowledge/concepts/concept-grantha-vatteluttu-and-tamil-script-evolution-on-palm-leaf.md",
        "slug": "concept-grantha-vatteluttu-and-tamil-script-evolution-on-palm-leaf",
        "category": "concept",
        "name_en": "Tamil Script Evolution on Palm Leaf: Vatteluttu Round Script, Grantha Sanskrit Characters & Medieval Tamil Script Standardization",
        "name_ta": "ஓலையில் தமிழ் எழுத்து பரிணாமம் - வட்டெழுத்து வட்டல் எழுத்து, கிரந்த சமஸ்கிருத எழுத்துக்கள் மற்றும் இடைக்கால தமிழ் எழுத்து தரப்படுத்தல்",
        "era": "Sangam Era to Medieval Era",
        "year_start": -200,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "The evolution of Tamil script forms on palm-leaf media: early Brahmi-derivative Vatteluttu (round letter) script optimized for horizontal palm-leaf engraving, the parallel Grantha script developed for Sanskrit phonology within Tamil manuscripts, and the medieval standardization of modern Tamil script forms influenced by the material constraints of iron stylus on palmyra.",
        "summary_ta": "ஓலையில் தமிழ் எழுத்து வடிவ பரிணாமம்: ஆரம்ப பிராமி-வழிவந்த வட்டெழுத்து, கிரந்த எழுத்து மற்றும் இரும்பு எழுத்தாணியின் பொருள்முறை நிலைமைகளால் பாதிக்கப்பட்ட இடைக்கால தமிழ் எழுத்து தரப்படுத்தல்.",
        "sources": [
            "Tamil Epigraphy and Palaeography (K.V. Subrahmanya Aiyer)",
            "History of Tamil Script",
            "South Asian Script Studies Journal"
        ],
        "content": "# Tamil Script Evolution on Palm Leaf\n\nPalm-leaf material properties directly shaped the evolution of Tamil script letter forms:\n\n**Vatteluttu (வட்டெழுத்து) — Round Script (c. 300 BCE–900 CE):**\nThe name literally means \"round letters.\" The rounded forms are NOT decorative — they are functionally optimal for iron stylus on palm leaf. Straight lines (like those in Brahmi) risk splitting the leaf along vascular bundle planes when the stylus moves against the leaf grain. Rounded strokes move *with* the leaf structure, following the natural curve of vascular bundles without tearing.\n\n**Grantha Script:**\nWhen Tamil scribes needed to transcribe Sanskrit phonemes absent in Tamil (aspirated stops, retroflex sibilants, dental fricatives), they developed Grantha script — a parallel system using modified letter forms within the same palm-leaf manuscript. Thousands of bilingual Tamil-Sanskrit manuscripts from Thanjavur use Grantha letters interspersed in Tamil sentences.\n\n**Medieval Standardization (c. 700–1200 CE):**\nBy the Pallava-Chola period, stylus mechanics pushed letter forms toward the \"square-with-rounded-corner\" profile of modern Tamil: short horizontal top strokes (following vascular bundles), verticals and curves drawn in smooth strokes. The *kombu* (curved superscript vowel markers) were standardized as single graceful arcs across the consonant top — easily drawn in one stylus stroke."
    },
    {
        "file": "knowledge/technologies/technology-manuscript-colophon-correction-and-inter-leaf-annotation-system.md",
        "slug": "technology-manuscript-colophon-correction-and-inter-leaf-annotation-system",
        "category": "technology",
        "name_en": "Manuscript Error Correction: Copper-Scrape Erasure, Oil-Fill Concealment & Marginal Annotation Inter-Leaf System",
        "name_ta": "சுவடி பிழை திருத்தம் - செம்பு கீறி அழிக்கல், எண்ணெய் நிரப்பி மறைத்தல் மற்றும் விளிம்பு குறிப்பு இடை-ஓலை முறை",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Traditional error correction and annotation technologies in Tamil palm-leaf manuscripts: copper scrape erasure of engraved errors (re-smoothing the groove), lamp-black oil filling of unintended marks, the convention of inserting correction leaves between folios rather than defacing primary text, and the marginal annotation system using the leaf edge strip.",
        "summary_ta": "பாரம்பரிய தமிழ் ஓலைச்சுவடி பிழை திருத்தம் மற்றும் குறிப்பு: செம்பு கீறி பிழை அழிக்கல், தீக்கரி எண்ணெய் நிரப்பி தடம் மறைத்தல், முதன்மை உரையை சேதப்படுத்தாமல் திருத்த ஓலைகளை இடைவைக்கும் மரபு மற்றும் விளிம்பு குறிப்பு முறை.",
        "sources": [
            "Palm Leaf Manuscript Codicology",
            "Indian Manuscript Conservation Manual",
            "South Asian Archive Studies"
        ],
        "content": "# Manuscript Error Correction & Annotation Systems\n\nEngraved palm-leaf text cannot be \"erased\" in the conventional sense — the groove physically displaces leaf material. Traditional Tamil scribes developed three correction techniques:\n\n**1. Copper-Scrape Erasure (*Thamba Chekku*):**\nA flat copper blade (5 cm long, 1 mm thick) is pressed firmly across the erroneous groove and dragged laterally. The malleable copper shears off the raised groove edges and gently compresses the groove floor upward. The resulting surface is smoother than the original but slightly raised. A re-engraving can be made in this zone, though it is never as crisp as first-time engraving.\n\n**2. Oil-Fill Concealment (*Ennai Niraippu*):**\nFor accidental short scratches or stray marks, coconut oil is dripped into the erroneous groove and allowed to cure for 24 hours. The hardened oil fills the groove flush with the leaf surface; subsequent *karumbu-podi* application does not adhere to the oil-filled area, leaving the error invisible in the final text.\n\n**3. Correction Folio Insertion (*Thiruppai Olai*):**\nFor large-scale errors affecting multiple lines, the standard convention was to discard the damaged folio and insert a corrected replacement folio at the same position in the threading. The discarded folio is never destroyed — it is marked with a correction symbol and stored separately as archival evidence of the scribal session."
    },
    {
        "file": "knowledge/places/place-alwarthirunagari-ancient-palm-leaf-scriptorium-haven.md",
        "slug": "place-alwarthirunagari-ancient-palm-leaf-scriptorium-haven",
        "category": "place",
        "name_en": "Alwarthirunagari: Ancient Tamil Palm-Leaf Scriptorium Haven, Nammalwar Shrine & Living Chuvadi Manuscript Tradition",
        "name_ta": "ஆழ்வார்திருநகரி - பண்டைய தமிழ் ஓலைச்சுவடி நூலக தளம், நம்மாழ்வார் திருக்கோயில் மற்றும் உயிர்ப்புள்ள சுவடி பாரம்பரியம்",
        "era": "Early Medieval to Modern Era",
        "year_start": 700,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Historic sacred Vaishnava pilgrimage town and manuscript scriptorium capital on the Tamirabarani River in Tirunelveli district, home of the Alvars saint-poet Nammalwar and the most significant palm-leaf manuscript copying scriptorium in classical Tamil literature, preserving the Naalayira Divyaprabandham through centuries of hereditary scribal tradition.",
        "summary_ta": "திருநெல்வேலி மாவட்டத்தில் தாமிரபரணி நதிக்கரையில் வரலாற்று புனித வைணவ யாத்திரை நகரம் மற்றும் கைவரிசை நூலகத் தலைநகரம்: நம்மாழ்வாரின் ஊர் மற்றும் நாலாயிர திவ்யப்பிரபந்தம் பாதுகாத்த சிறந்த ஓலைச்சுவடி நகல் நூலகம்.",
        "sources": [
            "Alwarthirunagari Temple History",
            "Nammalwar and the Alvars: Bhakti Literature Studies",
            "Tirunelveli District Cultural Heritage Survey"
        ],
        "content": "# Alwarthirunagari: Scriptorium Haven\n\nAlwarthirunagari (also *Thirukurugur*) in Tirunelveli district is simultaneously a premier Vaishnava pilgrimage site and the most important historical center of Tamil palm-leaf manuscript culture.\n\n**Geographic Setting:**\nLocated on the southern bank of the Tamirabarani River, 7 km east of Ambasamudram. The river's regulated flood plains (*aazham*) supported dense Borassus palmyra (*pana*) groves — the raw material for the scriptorium. River humidity (60–70% RH year-round) is optimal for manuscript storage without excessive cracking or fungal growth.\n\n**Nammalwar's Legacy:**\nNammalwar (c. 700–800 CE), the greatest of the 12 Alvars, composed all 1,296 verses of the *Tiruvaimozhi* (the Tamil Veda equivalent) here. The immense prestige of this compositional legacy drew scribal families to Alwarthirunagari for over a millennium to copy and preserve the Divyaprabandham corpus.\n\n**The Living Tradition:**\nEven today, a few master scribes (*ezhuttalar*) in Alwarthirunagari practice the traditional iron-stylus palm-leaf engraving for religious commissions — producing astrological horoscopes (*jathagam*), temple renovation inscriptions (*sthapana olai*), and medicinal texts (*vaidya chuvadi*) in the ancient manuscript format."
    }
]

EDGES = [
    [
        "text-tolkappiyam-and-agastiyam-colophons-on-olai-chuvadi-engraving-and-manuscript-preservation",
        "ATTESTS",
        "technology-olai-leaf-harvesting-boiling-smoking-and-pressing-for-manuscript-preparation",
        "core",
        "Sangam Era",
        "Tolkappiyam colophons directly describe the scribal preparation of palm-leaf folios",
        "Tolkappiyam Mudivurai Inscriptions"
    ],
    [
        "technology-olai-leaf-harvesting-boiling-smoking-and-pressing-for-manuscript-preparation",
        "PRODUCES",
        "concept-borassus-palmyra-leaf-cellular-structure-and-stylus-engraving-mechanics",
        "core",
        "Iron Age to Modern Era",
        "The four-stage leaf preparation exploits and enhances the natural silica phytolith properties",
        "Tamil Manuscript Conservation Techniques"
    ],
    [
        "artifact-ezhuthani-iron-stylus-knife-and-soot-rubbing-pad",
        "IMPLEMENTS",
        "concept-borassus-palmyra-leaf-cellular-structure-and-stylus-engraving-mechanics",
        "core",
        "Iron Age to Modern Era",
        "The ezhuthani stylus tip geometry is optimized for the specific silica phytolith hardness of Borassus leaf",
        "Tamil Nadu Manuscript Library Tool Catalog"
    ],
    [
        "technology-chuvadi-binding-threading-hair-cord-and-wooden-cover-boards",
        "PRESERVES",
        "concept-palm-leaf-manuscript-humidity-temperature-and-long-term-archival-chemistry",
        "core",
        "Iron Age to Modern Era",
        "Hair-cord threading exploits identical humidity expansion coefficients of hair and leaf to preserve manuscript integrity",
        "South Asian Book History"
    ],
    [
        "institution-alwarthirunagari-chuvadi-scriptorium-guild-of-master-scribes-and-copyists",
        "HOSTED",
        "place-alwarthirunagari-ancient-palm-leaf-scriptorium-haven",
        "core",
        "Early Medieval to Modern Era",
        "The scriptorium guild operated from Alwarthirunagari on the Tamirabarani River",
        "Alwarthirunagari Temple Records"
    ],
    [
        "concept-grantha-vatteluttu-and-tamil-script-evolution-on-palm-leaf",
        "ADAPTS_TO",
        "concept-borassus-palmyra-leaf-cellular-structure-and-stylus-engraving-mechanics",
        "core",
        "Sangam Era to Medieval Era",
        "Vatteluttu round letter forms evolved specifically to exploit palm leaf vascular bundle architecture",
        "Tamil Epigraphy and Palaeography"
    ],
    [
        "technology-manuscript-colophon-correction-and-inter-leaf-annotation-system",
        "APPLIES",
        "artifact-ezhuthani-iron-stylus-knife-and-soot-rubbing-pad",
        "core",
        "Iron Age to Modern Era",
        "Error correction uses the copper trimming knife component of the scribal toolkit",
        "Palm Leaf Manuscript Codicology"
    ],
    [
        "institution-alwarthirunagari-chuvadi-scriptorium-guild-of-master-scribes-and-copyists",
        "COPIED",
        "text-tolkappiyam-and-agastiyam-colophons-on-olai-chuvadi-engraving-and-manuscript-preservation",
        "core",
        "Early Medieval to Modern Era",
        "Alwarthirunagari scriptorium preserved and copied both Tolkappiyam and Agastiyam traditions",
        "Naalayira Divyaprabandham Manuscript History"
    ],
    [
        "concept-palm-leaf-manuscript-humidity-temperature-and-long-term-archival-chemistry",
        "APPLIES_TO",
        "place-alwarthirunagari-ancient-palm-leaf-scriptorium-haven",
        "core",
        "Iron Age to Modern Era",
        "Tamirabarani River humidity microclimate at Alwarthirunagari is chemically ideal for manuscript preservation",
        "Conservation Science Archive Studies"
    ],
    [
        "technology-olai-leaf-harvesting-boiling-smoking-and-pressing-for-manuscript-preparation",
        "PROTECTS",
        "concept-palm-leaf-manuscript-humidity-temperature-and-long-term-archival-chemistry",
        "core",
        "Iron Age to Modern Era",
        "Neem-smoke curing and turmeric treatment address the specific fungal and insect decay vectors of tropical archival chemistry",
        "Traditional Palm Leaf Preparation Methods"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 39: Ancient Tamil Palmyra Palm-Leaf Manuscript Writing, Iron Stylus Ezhuthani Engraving & Chuvadi Scriptorium Guild Traditions...")
    
    # Phase 1: Write Dossiers
    print("Phase 1: Writing Markdown Dossiers...")
    for d in DOSSIERS:
        fpath = os.path.join(MOOLAM_KNOWLEDGE, d["file"])
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"  ✓ Written: {d['file']}")

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Phase 2: Upsert Lore Nodes
    print("Phase 2: Upserting Lore Nodes...")
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
                properties = EXCLUDED.properties;
        """, (
            str(uuid.uuid4()), slug, d["category"], d["name_en"], d["name_ta"],
            d["era"], d["year_start"], d["year_end"], d.get("thinai"),
            d["summary_en"], d["summary_ta"], d["sources"], "core", props
        ))
        nodes_upserted += 1
        print(f"  ✓ Upserted node: {slug}")
    conn.commit()

    # Phase 3: Insert Lore Edges
    print("Phase 3: Inserting Lore Edges...")
    edges_inserted = 0
    for edge in EDGES:
        src, rel, tgt, layer, era, desc, evidence = edge
        cur.execute("""
            DELETE FROM lore_edges
            WHERE source_slug = %s AND relation_type = %s AND target_slug = %s;
        """, (src, rel, tgt))
        cur.execute("""
            INSERT INTO lore_edges (
                id, source_slug, relation_type, target_slug, layer, era,
                description, evidence_source
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            );
        """, (
            str(uuid.uuid4()), src, rel, tgt, layer, era, desc, evidence
        ))
        edges_inserted += 1
        print(f"  ✓ Linked: ({src}) --[{rel}]-> ({tgt})")
    conn.commit()

    # Phase 4: Embed & Insert RAG Chunks
    print("Phase 4: Embedding RAG Chunks with bge-m3:latest...")
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

    print(f"Ingestion Complete for Batch 39 Corpus! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
