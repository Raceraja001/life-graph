#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Temple Stone Inscription Epigraphy, Vatteluttu Chisel Engraving & Copper-Plate Scribing
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
        "file": "knowledge/texts/text-velvikudi-grant-bilingual-sanskrit-tamil-copper-plate-charter-of-nedunjadayan.md",
        "slug": "text-velvikudi-grant-bilingual-sanskrit-tamil-copper-plate-charter-of-nedunjadayan",
        "category": "text",
        "name_en": "Velvikudi Grant: Historic 8th-Century Bilingual Copper-Plate Charter of Jatila Parantaka Nedunjadayan",
        "name_ta": "வேள்விக்குடி செப்பேடு - எட்டாம் நூற்றாண்டு சமஸ்கிருதம் மற்றும் தமிழ் இருமொழி சாசனப் பிரகடனம்",
        "era": "Early Medieval Era",
        "year_start": 765,
        "year_end": 775,
        "thinai": "marutham",
        "summary_en": "The famous 8th-century CE Velvikudi copper-plate charter issued by Pandyan King Jatila Parantaka Nedunjadayan (Nedunjeliyan), consisting of ten engraved copper sheets bound by an embossed seal ring, recording in majestic Sanskrit and Vatteluttu Tamil the restoration of an ancient village land grant to a Vedic scholar.",
        "summary_ta": "எட்டாம் நூற்றாண்டில் பாண்டிய மன்னன் பராந்தக நெடுஞ்சடையன் வெளியிட்ட வரலாற்றுப் புகழ்பெற்ற வேள்விக்குடி செப்பேடு: பத்து தாமிரத் தகடுகள், முத்திரை வளையம், சமஸ்கிருத-வட்டெழுத்து தமிழ் இருமொழிப் பிரகடனம் மற்றும் நில உரிமை மீட்பு ஆவணம்.",
        "sources": [
            "Epigraphia Indica Vol. XVII: The Velvikudi Grant",
            "Pandyan History and Epigraphy",
            "Archaeological Survey of India"
        ],
        "content": "# Velvikudi Grant: Royal Pandyan Diplomatics\n\nDiscovered in Madurai district, the *Velvikudi Grant* (c. 770 CE) is one of the supreme monuments of South Indian legal diplomatics and metallurgical epigraphy:\n\n**Historical Context:**\nA citizen named Narkorran approached the Pandyan king in his palace at Madurai, pleading that the village of Velvikudi—originally granted to his ancestor by Sangam monarch Palyagasalai Mudukudumi Peruvaludhi—had been illegally confiscated during the Kalabhra interregnum. King Nedunjadayan examined ancient village archival records (*pazham-kanakku*), confirmed the ancient title, and formally re-granted the land, commanding his court scribes to record the deed on copper plates (*chembettu*).\n\n**Physical Architecture of the Charter:**\n- **Ten Heavy Copper Sheets**: Measuring 28 cm × 9 cm, with raised margins (*kattu*) to protect the incised lettering from frictional abrasion.\n- **Massive Bronze Ring**: A circular bronze ring (10 cm diameter, 1.2 kg) passes through holes bored in the left margin of all ten plates.\n- **Royal Pandya Bull & Double-Fish Seal**: The ends of the ring are fused into a cast bronze medallion bearing the Pandyan dynastic insignia: two fish (*kayal*), a recumbent Nandi bull, an umbrella (*chhatra*), and fly-whisks (*chamara*)."
    },
    {
        "file": "knowledge/concepts/concept-epigraphical-palaeography-vatteluttu-evolution-and-chisel-incising-kinematics.md",
        "slug": "concept-epigraphical-palaeography-vatteluttu-evolution-and-chisel-incising-kinematics",
        "category": "concept",
        "name_en": "Tamil Epigraphical Palaeography: Vatteluttu Chisel Incising Kinematics and Letter Morphometrics",
        "name_ta": "தமிழ் கல்வெட்டியல் எழுத்துப் பரிணாமம்: வட்டெழுத்து உளி வெட்டு இயக்கவியல் மற்றும் எழுத்துரு வடிவம்",
        "era": "Iron Age to Medieval Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "marutham",
        "summary_en": "Palaeographical evolution of ancient Tamil scripts from Tamil-Brahmi through Vatteluttu to Medieval Grantha-Tamil: biomechanics of the stonemason's hammer and chisel strokes, curve-cutting dynamics in crystalline granite, and the physical constraints of stone cleavage dictating letter ductus.",
        "summary_ta": "தமிழ்-பிராமி முதல் வட்டெழுத்து வரை தமிழ் வரிவடிவப் பரிணாமம்: கருங்கல்லில் உளி வெட்டும் இயக்கவியல், வளைவு வெட்டு முறை மற்றும் பாறை பிளக்கும் இயற்பியல் எவ்வாறு எழுத்து வடிவங்களை வடிவமைத்தது என்ற அறிவியல்.",
        "sources": [
            "Mahadevan: Early Tamil Epigraphy",
            "Indian Epigraphy (D.C. Sircar)",
            "Journal of the Epigraphical Society of India"
        ],
        "content": "# Vatteluttu Epigraphy & Chisel Kinematics\n\nThe physical shape of classical Tamil scripts was fundamentally shaped by the mechanics of chisel impacts on hard charnockite granite:\n\n**From Angular Brahmi to Curvilinear Vatteluttu:**\nEarly Tamil-Brahmi (3rd century BCE to 2nd century CE) featured straight, geometric strokes easily scratched onto soft cave sandstones and potsherds. However, when scribes began carving into hard plutonic granites under the Pandyas and Cheras, straight lines frequently caused rock cleavage along crystal boundaries.\n- **Vatteluttu (Round Script)**: Developed specifically to mitigate rock fracture. Rounded arcs distributed impact stress evenly across quartz and feldspar grain boundaries, preventing brittle chips (*sedhil*) from flying off and defacing the inscription.\n\n**Chisel Impact Kinematics:**\n1. **Pilot Chipping (*Kuri-Idudhal*)**: The epigrapher (*sasana-sirpi*) used a sharp diamond-pointed iron punch (*vaira-vusi*) held at 60° to tap tiny pilot depressions outlining the letter.\n2. **Channel Engraving (*Vari-Vettudhal*)**: A narrow flat-edged chisel (3 mm cutting width) was driven along the pilot line by rapid, low-momentum wooden mallet taps (100–120 strikes per minute).\n3. **V-Profile Trough**: The ideal cut formed a clean, triangular V-groove with 45° sloping sidewalls, allowing natural light to cast high-contrast internal shadows that rendered letters legible from distance."
    },
    {
        "file": "knowledge/technologies/technology-copper-plate-lost-wax-sheet-hammering-ring-soldering-and-royal-seal-casting.md",
        "slug": "technology-copper-plate-lost-wax-sheet-hammering-ring-soldering-and-royal-seal-casting",
        "category": "technology",
        "name_en": "Chembettu Metallurgy: Copper Plate Cold-Hammering, Edge Piercing, Bronze Ring Soldering & Royal Seals",
        "name_ta": "செப்பேடு வார்ப்பு நுட்பம்: தாமிரத் தகடு அடிப்பு, ஓரத் துளையிடல், வெண்கல வளைய இணைப்பு மற்றும் முத்திரை",
        "era": "Early Medieval to Medieval Era",
        "year_start": 500,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "Metallurgical fabrication of royal copper-plate charters (chembettu): casting copper ingots, repetitive cold-hammering and annealing into uniform 2-3 mm sheets, planar polishing with river silt, graver incision of text, punch-piercing, and lost-wax casting of lead-bronze heraldic royal seal rings.",
        "summary_ta": "அரச செப்பேடுகள் உருவாக்கும் உலோகவியல் நுட்பம்: தாமிரத்தை உருக்கி தட்டித் தகடாக்குதல், ஆற்று வண்டல் கொண்டு பளபளப்பாக்குதல், எஃகு உளிகளால் எழுத்துக்கள் பொறித்தல் மற்றும் வெண்கல முத்திரை வளையம் வார்த்தல்.",
        "sources": [
            "Archaeometallurgy of South Indian Copper Charters",
            "Bulletin of the Madras Government Museum",
            "Ancient Metallurgy of India"
        ],
        "content": "# Chembettu Metallurgy: Fabrication of Royal Charters\n\nRoyal copper-plate charters (*chembettu* or *tamrasasana*) were legal title-deeds designed to endure for eternity (*a-chandrarkam*):\n\n**1. Sheet Forging & Annealing:**\nSmelted copper ingots (98.5% Cu, with trace iron and arsenic) were cast into rectangular bars and beaten flat using heavy iron sledges. Because repetitive cold-working induces strain-hardening and micro-cracking, sheets underwent cyclic annealing—heated to dull red ($600^{\\circ}\\text{C}$) over charcoal forges and quenched in sour fermented rice wash (*kaadi*) to strip cupric oxide scale. The resulting sheets measured 2.0–3.0 mm thick with planished mirror surfaces.\n\n**2. Protective Raised Rims (*Kattu*):**\nThe margins of each plate were cold-hammered upward to form raised perimeter flanges (2 mm high). When multiple plates were strung together on a ring, the raised borders kept the inscribed surfaces from rubbing against each other, preserving delicate lettering against centuries of friction.\n\n**3. Graver Engraving:**\nCourt calligraphers painted characters onto the plate using carbon ink. Master coppersmiths (*chempu-kothan*) engraved the lines using hardened steel burins (*vettu-vusi*), displacing curly copper shavings.\n\n**4. Casting the Dynastic Seal:**\nThe plates were threaded onto a heavy copper-bronze rod. The open ends were joined inside a refractory clay mold, into which molten bronze (82% Cu, 14% Sn, 4% Pb) was poured using the lost-wax technique, casting an inviolable royal seal bearing the monarch's heraldic crest."
    },
    {
        "file": "knowledge/artifacts/artifact-chembettu-copper-plates-bronze-bull-seals-and-hardened-steel-gravers.md",
        "slug": "artifact-chembettu-copper-plates-bronze-bull-seals-and-hardened-steel-gravers",
        "category": "artifact",
        "name_en": "Chembettu Copper Charters, Cast Bronze Pandya Bull Seals and Hardened Steel Burin Gravers",
        "name_ta": "செப்பேட்டுத் தொகுதி, பாண்டிய கயல் மற்றும் காளை வெண்கல முத்திரைகள் மற்றும் எஃகு எழுத்து உளிகள்",
        "era": "Early Medieval to Medieval Era",
        "year_start": 600,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "Physical artifacts of medieval Tamil diplomatics: multi-leaf copper charter sets (chembettu), massive cast bronze royal seal rings featuring Pandyan double-fish and Chola tiger crests, and the hardened iron/steel engraving burins used by royal sasana-kollan artisans.",
        "summary_ta": "பண்டைய தமிழ் ஆவணக் கருவிகள்: பல ஏடுகள் கொண்ட செப்பேட்டுத் தொகுதிகள், பாண்டிய இரட்டைக் கயல் மற்றும் சோழப் புலி சின்னங்கள் தாங்கிய வெண்கல முத்திரைகள் மற்றும் எஃகு எழுது உளிகள்.",
        "sources": [
            "Madras Government Museum Copper Plate Catalogues",
            "Archaeological Heritage of Tamil Nadu",
            "Corpus of Pandyan Inscriptions"
        ],
        "content": "# Chembettu Charters & Royal Seals: Artifact Assemblage\n\nMuseum collections preserve exquisite examples of classical royal charters:\n\n**1. The Multi-Plate Assembly:**\nA complete charter consists of 5 to 31 copper plates. Each leaf features a circular ring-hole (1.5 to 2.5 cm diameter) punched in the middle of the left-hand margin. The plates are numbered using archaic Tamil numeral glyphs on the inner margins.\n\n**2. The Royal Medallion Seal:**\nThe seal represents the supreme legal authority of the crown:\n- **Pandyan Seals**: Depict two upright carps (*kayal*), a royal parasol flanked by chauris, an anchor, and a recumbent Nandi bull, surrounded by a Grantha metrical legend proclaiming the king's lineage.\n- **Chola Seals**: Feature the Chola tiger seated beside the Pandyan pair of fish and Chera bow, signifying imperial supremacy across all three kingdoms.\n- The ring cannot be opened without cutting or melting the seal; any severed ring immediately invalidated the land title in royal courts.\n\n**3. Vettu-Vusi (Hardened Steel Graver):**\nA 12 cm chisel with a diamond-section point forged from wootz crucible steel (*ukku*), tempered to extreme hardness (62–65 HRC) to easily incise ductile annealed copper without dulling."
    },
    {
        "file": "knowledge/concepts/concept-inscriptional-legal-diplomatics-meykeerthi-praises-and-boundary-survey-verifications.md",
        "slug": "concept-inscriptional-legal-diplomatics-meykeerthi-praises-and-boundary-survey-verifications",
        "category": "concept",
        "name_en": "Inscriptional Diplomatics: Royal Meykeerthi Eulogies, Circumambulatory Boundary Walking & Legal Formulas",
        "name_ta": "சாசன சட்டக் கோட்பாடு: மெய்க்கீர்த்தி வாழ்த்துப் பாடல், பிடி சூழ்ந்து எல்லை வகுத்தல் மற்றும் ஆவண நடைமுறை",
        "era": "Early Medieval to Medieval Era",
        "year_start": 700,
        "year_end": 1300,
        "thinai": "marutham",
        "summary_en": "The legal and diplomatic structure of Tamil epigraphical grants: standardized Meykeerthi poetic preambles establishing sovereign legitimacy, the ritual boundary walking ceremony (pidi-soozhndhu) where a female elephant delineated property perimeters, and tax-immunity clauses (karanmai and miyatchi).",
        "summary_ta": "தமிழ் கல்வெட்டுகளின் சட்ட வடிவமைப்பு: அரசரின் வீரப் புகழைப் பாடும் மெய்க்கீர்த்தி, பெண் யானையை நடத்தி எல்லைகளை வகுக்கும் 'பிடி சூழ்ந்து எல்லை குறித்தல்' முறை மற்றும் வரிவிலக்கு நிபந்தனைகள்.",
        "sources": [
            "Srinivasan: Studies in Tamil Epigraphy",
            "Nilakanta Sastri: The Pandyan Kingdom",
            "Legal Heritage of South India"
        ],
        "content": "# Inscriptional Diplomatics & Legal Formulas\n\nTamil epigraphs were rigorous legal instruments structured according to invariant administrative formulas:\n\n**1. The Meykeerthi (Royal Eulogy):**\nImperial inscriptions begin with an ornate poetic prologue (*Meykeerthi* / \"True Glory\") composed by court poets. It details the king's conquests, regnal year, queen consort, and moral virtues. Because each monarch adopted an individualized opening phrase (e.g., Rajaraja I's *Thirumagal Pola*, Jatavarman Sundara Pandya's *Samastha Jagadhadhara*), the Meykeerthi provides definitive dating markers for modern historians.\n\n**2. Pidi-Soozhndhu (The Elephant Boundary Walk):**\nTo define granted land, the royal charter records:\n> *\"The boundary of this village was determined by letting loose a female elephant (pidi-soozhndhu), and wherever she walked, stone boundary markers (kallu) and milk-bush shrubs (kalli) were planted...\"*\nRoyal surveyors (*Alavu-kanakkar*), village elders, and neighboring landowners walked together behind the elephant to witness and swear to the boundaries.\n\n**3. Tax Immunities (*Pariharam*):**\nThe charter explicitly lists all customary taxes abolished on the donated land: exemption from irrigation tolls (*neerkovai*), oil-press taxes (*chekku-ira*), weaver dues (*thari-irai*), and royal forage demands (*vetti-vedinai*)."
    },
    {
        "file": "knowledge/institutions/institution-sasana-kollan-and-perun-thatchar-corporation-of-royal-court-epigraphers.md",
        "slug": "institution-sasana-kollan-and-perun-thatchar-corporation-of-royal-court-epigraphers",
        "category": "institution",
        "name_en": "Sasana-Kollan & Perun-Thatchar Guild of Royal Court Calligraphers, Coppersmiths and Stone Engravers",
        "name_ta": "சாசனக் கொல்லன் மற்றும் பெருந்தச்சர் அரண்மனை ஆவணக் கழகம், கல்வெட்டுச் சிற்பிகள் மற்றும் எழுத்துக் குழு",
        "era": "Sangam Era to Medieval Era",
        "year_start": -300,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "The courtly institution of royal epigraphers, stone carvers, and goldsmith-engravers: hereditary masters holding royal titles such as Sasana-Kollan, Perun-Thatchar, and Rathakara, endowed with hereditary tax-free service lands (kaniyatchi) for maintaining royal architectural and epigraphical records.",
        "summary_ta": "அரசவை ஆவணக் கலைஞர்கள், கல்வெட்டுப் பெருந்தச்சர்கள் மற்றும் செப்பேட்டு சாசனக் கொல்லர்களின் அதிகாரப்பூர்வ கழகம்: மன்னர்களால் 'சாசனக் கொல்லன்' பட்டம் வழங்கப்பட்டு, பரம்பரை இறையிலி நிலங்கள் பெற்று ஆவணங்களை உருவாக்கிய கலைஞர்கள்.",
        "sources": [
            "Epigraphia Indica: Artisan Signatures",
            "Chola and Pandya Inscriptional Artisans",
            "Vishwa Karma Guild Studies"
        ],
        "content": "# Sasana-Kollan: Royal Epigrapher Guilds\n\nThe execution of royal charters was entrusted exclusively to hereditary master artisans endowed with judicial authority:\n\n**The Royal Signatures:**\nAt the conclusion of royal copper charters, the engraving master proudly signed his lineage:\n> *\"This copper charter was written by the royal coppersmith (Sasana-Kollan) Yuddhamalla, son of master craftsman Perun-Thatchan of Madurai, and to him was granted one share of land as scribal endowment...\"* (Velvikudi Colophon)\n\n**Artisan Hierarchy:**\n- **Sasana-Kollan**: Royal coppersmiths specializing in melting, engraving, and sealing multi-plate charters.\n- **Sirpa-Acharyan / Perun-Thatchan**: Chief architectural master who oversaw both the construction of stone vimanas and the carving of grand lithic inscriptions across temple basements (*adhisthana*).\n- **Kallu-Vettuvor**: Field stonemasons who manually hammered and chiseled the drafted chalk text onto stone courses.\n\n**Royal Privileges:**\nThese craftsmen were not mere laborers; they were high-status palace functionaries permitted to ride palanquins, wear gold ear ornaments, and sound conches during royal festivals."
    },
    {
        "file": "knowledge/technologies/technology-granite-dressed-surface-drafting-grid-chalking-and-relief-chisel-engraving.md",
        "slug": "technology-granite-dressed-surface-drafting-grid-chalking-and-relief-chisel-engraving",
        "category": "technology",
        "name_en": "Lithic Epigraphy Technology: Granite Surface Polishing, Grid Chalking and High-Relief Chisel Engraving",
        "name_ta": "கல்வெட்டு பொறிப்பு நுட்பம்: கருங்கல் மட்டமாக்கல், கட்டமிடல், மை பூசி வரைதல் மற்றும் உளி பொறிப்பு",
        "era": "Iron Age to Modern Era",
        "year_start": -300,
        "year_end": 1500,
        "thinai": "marutham",
        "summary_en": "Engineering sequence for monumental temple wall inscriptions: dressing crystalline granite plinths with emery stone rub-blocks to absolute planarity, snapping chalked guide strings for horizontal baseline alignment, brush drafting with lampblack/ochre ink, and incision carving using tempered iron chisels.",
        "summary_ta": "கோயில் சுவர்களில் கல்வெட்டு பொறிக்கும் துல்லியப் பொறியியல்: பாறையை மட்டமாக்குதல், நூல் பிடித்து கட்டமிடுதல், மை தூரிகையால் முன் வரைவு வரைதல் மற்றும் எஃகு உளியால் செதுக்கும் முழுமையான முறை.",
        "sources": [
            "Srinivasan: Architectural Techniques of the Cholas",
            "Studies in Stone Masonry of South India",
            "ASI Conservation Manual: Epigraphical Reliefs"
        ],
        "content": "# Monumental Lithic Epigraphy Engineering\n\nCarving thousands of words across the undulating molded basement courses (*adhisthana*) of stone temples required precise geometric discipline:\n\n**1. Surface Dressing & Abrasion:**\nThe granite ashlar blocks were hand-dressed with point chisels and smoothed by rubbing with corundum (*kurundam*) and wet river sand until all surface irregularities were under 0.5 mm.\n\n**2. Snapping Baseline Strings (*Nool-Pidithal*):**\nMaster masons snapped chalked cord lines (*kuri-nool*) across entire lengths of walls (often 40 to 60 meters long) to establish perfectly parallel horizontal baselines. Vertical guide marks maintained strict letter height (typically 4.0 to 6.0 cm for major temple texts).\n\n**3. Calligraphic Drafting:**\nA court scribe (*ezhuthalar*) painted the text directly onto the stone face using fine squirrel-hair brushes dipped in red ochre (*chemman*) or lampblack paste. This allowed proofreading before any chisel touched the rock.\n\n**4. Chisel Incision:**\nStonemasons (*kal-vettuvor*) hammered along the brush strokes with tempered steel chisels, cutting uniform V-grooves. Inscriptions were carved across joints between adjacent stone blocks seamlessly, proving the carving occurred *in situ* after the temple walls were completely erected."
    },
    {
        "file": "knowledge/places/place-velvikudi-ancient-pandya-copper-plate-grant-haven.md",
        "slug": "place-velvikudi-ancient-pandya-copper-plate-grant-haven",
        "category": "place",
        "name_en": "Velvikudi: Ancient Pandyan Royal Charter Haven, Vaigai Inscriptional Archives & Epigraphical Citadel",
        "name_ta": "வேள்விக்குடி - பண்டைய பாண்டியர் செப்பேட்டு சாசனத் தளம், வைகை ஆவணக் கூடம் மற்றும் கல்வெட்டு மையம்",
        "era": "Early Medieval to Modern Era",
        "year_start": 600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Historic agrarian village and inscriptional landmark in the fertile Vaigai River basin of Madurai district, celebrated as the historic findspot and origin of the Velvikudi grant, reflecting over a millennium of royal Pandyan legal archives, Vedic land grants, and classical epigraphical scholarship.",
        "summary_ta": "மதுரை மாவட்டத்தில் வைகை ஆற்றுப் படுகையில் அமைந்துள்ள வரலாற்று முக்கியத்துவம் வாய்ந்த கிராமம்: வேள்விக்குடி செப்பேட்டின் மூலத் தளம், பாண்டிய மன்னர்களின் ஆவணக் கூடம் மற்றும் நிலவுடைமை சட்ட சான்றுகளின் தலைநகரம்.",
        "sources": [
            "Madurai District Gazetteer",
            "ASI Epigraphical Discovery Reports: Velvikudi",
            "Pandyan Historical Topography"
        ],
        "content": "# Velvikudi: Epigraphical Sanctuary\n\nSituated along the alluvial banks of the Vaigai River basin near Madurai, Velvikudi represents the legal soul of Pandyan epigraphy:\n\n**Geographic & Archival Context:**\nThe village of Velvikudi was granted in the 3rd century CE by the Sangam Pandya monarch Palyagasalai Mudukudumi Peruvaludhi to the Vedic scholar Korkai-Kizhan Shivakumara Bhatta. Its location on fertile irrigated paddy lands made it an intensely valuable agricultural holding.\n\n**The Discovery of the Charter:**\nIn the early 20th century, the set of ten copper plates was recovered intact from an underground earthen vault near Velvikudi. Still bound by its unbroken royal bull seal, the plates preserve some of the finest surviving examples of 8th-century Pandyan Vatteluttu script.\n\n**Epigraphical Legacy:**\nThe Velvikudi grant remains the foundational document for constructing early Pandyan chronology, documenting nine generations of kings, military confrontations with the Pallavas, and the historic transition of Tamil society through the Kalabhra era."
    },
    {
        "file": "knowledge/concepts/concept-granite-weathering-erosion-patina-and-lithic-epigraphical-preservation.md",
        "slug": "concept-granite-weathering-erosion-patina-and-lithic-epigraphical-preservation",
        "category": "concept",
        "name_en": "Granite Weathering Geochemistry: Rain-Washing, Lichen Bio-Deterioration and Lithic Inscription Longevity",
        "name_ta": "கருங்கல் வேதியியல் வானிலைச் சிதைவு: மழை அரிப்பு, பாசி அரிப்பு மற்றும் கல்வெட்டு ஆயுள் பாதுகாப்பு",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Geochemical weathering dynamics of inscriptional granite in tropical climates: rainwater carbonation, feldspar hydrolysis into kaolinite clay, biological crusting by endolithic lichens, and the formation of protective iron-manganese rock varnish that preserves ancient Tamil carvings for millennia.",
        "summary_ta": "வெப்பமண்டல காலநிலையில் கருங்கல் கல்வெட்டுகளின் வானிலை வேதியியல்: மழைநீர் அமில அரிப்பு, பாறைப் பாசிகளால் ஏற்படும் சிதைவு மற்றும் கல்வெட்டுகளைக் காக்கும் இயற்கை இரும்பு-மாங்கனீசு பாதுகாப்பு அடுக்கு.",
        "sources": [
            "Journal of Cultural Heritage: Weathering of Granite Monuments",
            "Conservation Science: Lithic Inscriptions of South India",
            "Geochemistry of Tropical Rock Weathering"
        ],
        "content": "# Granite Weathering Geochemistry & Inscription Preservation\n\nThe remarkable thousand-year survival of Tamil stone inscriptions is governed by plutonic geochemistry and natural passivation:\n\n**Chemical Passivation (*Rock Varnish*):**\nOver centuries of alternating tropical monsoon rains and searing dry heat, trace iron ($Fe$) and manganese ($Mn$) ions within granite feldspars dissolve and migrate to the surface via capillary evaporation. They oxidize into an ultra-thin (5–50 μm), hard mineral patina called *desert varnish*. This natural ceramic-like glaze forms a hydrophobic seal over V-cut grooves, shielding them from abrasive windblown dust.\n\n**Degradation Vectors:**\n- **Hydrolysis**: Atmospheric carbonic acid ($\text{H}_2\text{CO}_3$) slowly converts orthoclase feldspar into soft kaolinite clay ($\text{Al}_2\text{Si}_2\text{O}_5\text{(OH)}_4$), causing granular crumbling (*sedhival*).\n- **Lichen Bio-corrosion**: Endolithic crustose lichens excrete oxalic acid, chelating calcium and iron cations and loosening surface mineral grains.\n\n**Protective Temple Architecture:**\nTamil temple architects deliberately positioned major narrative inscriptions along recessed plinth moldings (*kumuda* and *jagati*) beneath overhanging cornice eaves (*kodungai*), shielding them from direct torrential downpours."
    },
    {
        "file": "knowledge/artifacts/artifact-kalvettu-chisel-set-iron-punches-plummet-levels-and-inking-dabbers.md",
        "slug": "artifact-kalvettu-chisel-set-iron-punches-plummet-levels-and-inking-dabbers",
        "category": "artifact",
        "name_en": "Kalvettu Iron Burins, Hardened Diamond-Point Punches, Plummet Lines and Charcoal Inking Dabbers",
        "name_ta": "கல்வெட்டு உளித் தொகுப்பு, வைரக் கூர்மைப் பொன்கள், தூக்குநூல் மட்டம் மற்றும் மை தேய்க்கும் உருளைகள்",
        "era": "Iron Age to Modern Era",
        "year_start": -300,
        "year_end": 1500,
        "thinai": "marutham",
        "summary_en": "The stonemason's epigraphical carving toolset: hardened iron burins (vettu-vusi), conical diamond-point guide punches, lead plumb bobs (thookku-kundu) for vertical alignment, and silk-wrapped cotton dabbers used for making inked estampages on wet paper.",
        "summary_ta": "கல்வெட்டு செதுக்கும் கலைஞர்களின் கருவித் தொகுதி: எஃகு உளிகள், வைர முனை குத்து ஊசிகள், தூக்குநூல் மட்டம் மற்றும் கல்வெட்டு படிகள் எடுக்கும் மை உருளைகள்.",
        "sources": [
            "ASI Epigraphical Tools Catalog",
            "Traditional Stone Carving Implements of Mahabalipuram",
            "Tamil Epigraphy Field Manual"
        ],
        "content": "# Kalvettu Carving & Estampage Toolkit\n\nThe preservation and execution of lithic texts relied on precision iron implements:\n\n**1. Vettu-Uli (Lettering Chisels):**\nSmall, hand-forged chisels (10 to 15 cm long) with ultra-narrow cutting tips (2 to 5 mm). Forged with a dual-bevel cutting wedge tempered in oil to withstand thousands of high-velocity mallet taps against crystalline quartz without snapping or rolling edges.\n\n**2. Kuri-Vusi (Center Punch):**\nA short, conical pointed punch with a 60° hardened tip used to stamp pilot indentations along complex curves (such as the loops of Vatteluttu letters *ya*, *ra*, and *la*).\n\n**3. Thookku-Kundu (Plummet Level):**\nA cast bronze or lead plumb bob suspended by a raw silk thread, ensuring absolute verticality of text columns and architectural plinth alignments.\n\n**4. Mai-Pori (Inking Dabber / Estampage Pad):**\nUsed by traditional epigraphers and modern ASI scholars: a palm-sized pad of soft horsehair and cotton batting wrapped in fine, lint-free Chinese silk. Dabbed in black ink made from lampblack, gum arabic, and water, it is gently tapped over dampened handmade rag paper pressed into the incised grooves, producing high-fidelity white-on-black paper estampages."
    }
]

EDGES = [
    [
        "text-velvikudi-grant-bilingual-sanskrit-tamil-copper-plate-charter-of-nedunjadayan",
        "ISSUED_FROM",
        "place-velvikudi-ancient-pandya-copper-plate-grant-haven",
        "core",
        "Early Medieval Era",
        "The Velvikudi grant was issued to restore land title in the village of Velvikudi",
        "Epigraphia Indica XVII"
    ],
    [
        "technology-copper-plate-lost-wax-sheet-hammering-ring-soldering-and-royal-seal-casting",
        "MANUFACTURES",
        "artifact-chembettu-copper-plates-bronze-bull-seals-and-hardened-steel-gravers",
        "core",
        "Early Medieval to Medieval Era",
        "Cold-hammering and lost-wax casting produced the finished copper-plate charters",
        "Archaeometallurgy of South Indian Copper Charters"
    ],
    [
        "concept-epigraphical-palaeography-vatteluttu-evolution-and-chisel-incising-kinematics",
        "EXPLAINS",
        "technology-granite-dressed-surface-drafting-grid-chalking-and-relief-chisel-engraving",
        "core",
        "Iron Age to Medieval Era",
        "Chisel-impact kinematics explain why round Vatteluttu letters evolved to prevent stone chipping",
        "Mahadevan Early Tamil Epigraphy"
    ],
    [
        "artifact-kalvettu-chisel-set-iron-punches-plummet-levels-and-inking-dabbers",
        "IMPLEMENTS",
        "technology-granite-dressed-surface-drafting-grid-chalking-and-relief-chisel-engraving",
        "core",
        "Iron Age to Modern Era",
        "Narrow lettering chisels and center punches carved monumental temple inscriptions",
        "ASI Epigraphical Tools Catalog"
    ],
    [
        "concept-inscriptional-legal-diplomatics-meykeerthi-praises-and-boundary-survey-verifications",
        "STRUCTURES",
        "text-velvikudi-grant-bilingual-sanskrit-tamil-copper-plate-charter-of-nedunjadayan",
        "core",
        "Early Medieval Era",
        "Legal diplomatics and the elephant boundary-walk structured the Velvikudi charter",
        "Srinivasan Studies in Tamil Epigraphy"
    ],
    [
        "institution-sasana-kollan-and-perun-thatchar-corporation-of-royal-court-epigraphers",
        "ENGRAVED",
        "text-velvikudi-grant-bilingual-sanskrit-tamil-copper-plate-charter-of-nedunjadayan",
        "core",
        "Early Medieval Era",
        "Royal coppersmith Yuddhamalla signed the Velvikudi grant as official court engraver",
        "Velvikudi Colophon Inscription"
    ],
    [
        "concept-granite-weathering-erosion-patina-and-lithic-epigraphical-preservation",
        "PRESERVES",
        "technology-granite-dressed-surface-drafting-grid-chalking-and-relief-chisel-engraving",
        "core",
        "Iron Age to Modern Era",
        "Natural iron-manganese rock varnish preserved carved granite inscriptions for centuries",
        "Journal of Cultural Heritage"
    ],
    [
        "institution-sasana-kollan-and-perun-thatchar-corporation-of-royal-court-epigraphers",
        "OPERATED_AT",
        "place-velvikudi-ancient-pandya-copper-plate-grant-haven",
        "core",
        "Early Medieval to Medieval Era",
        "Royal scribes and surveyors verified ancient land boundaries on site at Velvikudi",
        "Pandyan Historical Topography"
    ],
    [
        "artifact-chembettu-copper-plates-bronze-bull-seals-and-hardened-steel-gravers",
        "DISCOVERED_AT",
        "place-velvikudi-ancient-pandya-copper-plate-grant-haven",
        "core",
        "Early Medieval to Modern Era",
        "The ten copper plates and bronze seal were discovered preserved near Velvikudi",
        "Madras Government Museum Catalogues"
    ],
    [
        "concept-epigraphical-palaeography-vatteluttu-evolution-and-chisel-incising-kinematics",
        "INFLUENCES",
        "artifact-chembettu-copper-plates-bronze-bull-seals-and-hardened-steel-gravers",
        "core",
        "Early Medieval to Medieval Era",
        "Palaeographical script evolution is embodied in the incised lettering of the plates",
        "Corpus of Pandyan Inscriptions"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 40: Ancient Tamil Temple Stone Inscription Epigraphy, Vatteluttu Chisel Engraving & Copper-Plate Scribing...")
    
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

    print(f"Ingestion Complete for Batch 40 Corpus! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
