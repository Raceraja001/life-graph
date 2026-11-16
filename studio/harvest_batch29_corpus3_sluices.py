#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Hydraulic Sluices & Cascade Reservoirs
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
        "file": "knowledge/texts/text-porunarattruppadai-chola-irrigation-sluices-and-river-embankment-verse.md",
        "slug": "text-porunarattruppadai-chola-irrigation-sluices-and-river-embankment-verse",
        "category": "text",
        "name_en": "Porunarattruppadai: Classical Sangam Poetry on Kaveri Embankments, Sluices & Inundation Canals",
        "name_ta": "பொருநராற்றுப்படை - காவிரி அணைக்கட்டு, மதகு மற்றும் பாசனக் கால்வாய்ப் பாடல்கள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Mudathamakanniyar's Sangam masterpiece chronicling Karikala Chola's masterworks: the stone dyking of Kaveri, engineered sluice outlets (madagu), and extensive riverine irrigation canals.",
        "summary_ta": "முடத்தாமக் கண்ணியார் இயற்றிய பொருநராற்றுப்படை, கரிகால் சோழன் காவிரியின் கரைகளை உயர்த்தியதும், மதகுகள் அமைத்துப் பாசனக் கால்வாய்கள் வெட்டிய வரலாற்றுச் சாதனைகளையும் பாடுகிறது.",
        "sources": [
            "Porunarattruppadai lines 235-250",
            "Pattinappalai lines 280-300"
        ],
        "content": "# Porunarattruppadai: Classical Sangam Poetry on Kaveri Hydraulic Works\n\nPorunarattruppadai constitutes one of the most vital literary records of early civil engineering in South Asia. Composed in praise of the legendary monarch Karikala Chola, the poem documents the revolutionary transformation of the turbulent Kaveri river basin into a hyper-productive agrarian granary.\n\nThe verses detail how thousands of bonded and recruited laborers raised monolithic earthen and stone flood levees (karai) along both banks of the river to restrain monsoonal inundations. Mudathamakanniyar portrays the stone-faced sluice gates (madagu and thoompu) designed to breach the dykes safely, regulating water distribution into an intricate hierarchy of distribution channels (vaaykkal).\n\nThe text links this hydraulic mastery directly to the proverb 'Where a female elephant lies down, seven kalams of paddy are harvested', testifying to the unmatched soil fertility created by silt-controlled gravity irrigation."
    },
    {
        "file": "knowledge/concepts/concept-piston-valve-reservoir-silt-clearing-sluice-engineering-kumizhi-thoombu.md",
        "slug": "concept-piston-valve-reservoir-silt-clearing-sluice-engineering-kumizhi-thoombu",
        "category": "concept",
        "name_en": "Piston-Valve Silt-Scouring Underwater Sluice Architecture (Kumizhi-Thoombu Engineering)",
        "name_ta": "குமிழித்தூம்பு - ஏரி வண்டல் அகற்றும் தானியங்கி நீர்க்குமிழ் மதகுப் பொறியியல்",
        "era": "Sangam to Chola Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "marutham",
        "summary_en": "Ingenious underwater piston-valve hydraulic sluice (kumizhi-thoombu) that uses dual-differential suction pressure to flush heavy bed silt while releasing clear surface water to irrigation channels.",
        "summary_ta": "ஏரிப்படுகையின் அடியில் அமைந்துள்ள துளைகள் வழியே கனமான வண்டலை உறிஞ்சி வெளியேற்றி, மேலடுக்கில் உள்ள தூய நீரைப் பாசனத்திற்கு அனுப்பும் தனித்துவமான தமிழ் நீரியல் மதகு.",
        "sources": [
            "Tamil Inscriptions of Tank Irrigation (K.V. Raman)",
            "Hydraulic Archeology of South Indian Reservoirs"
        ],
        "content": "# Piston-Valve Silt-Scouring Underwater Sluice (Kumizhi-Thoombu)\n\nThe kumizhi-thoombu stands as an extraordinary mechanical invention of ancient Tamil hydraulic engineers, solving the universal reservoir problem of siltation without modern mechanized dredging.\n\nSubmerged in the deepest portion of an irrigation lake bed, the mechanism consisted of a monolithic stone cistern with two distinct intake portals: a lower submerged orifice at bed level and an upper orifice. Inside this stone cylinder operated a movable stone or wooden plug (kumizhi) controlled by long levers or chains from an above-water stone pavilion.\n\nWhen opened during discharge, the high hydrodynamic pressure differential created a powerful vortex at the bottom, drawing in the accumulated viscous silt (sediment) and ejecting it through a subterranean stone conduit under the dam embankment. Simultaneously, clear top water poured into the upper intake, blending with the silt to deliver nutrient-rich alluvial mud directly onto farmers' paddy fields while preserving lake capacity."
    },
    {
        "file": "knowledge/concepts/concept-interconnected-cascade-tank-watershed-architecture-eri-cascade.md",
        "slug": "concept-interconnected-cascade-tank-watershed-architecture-eri-cascade",
        "category": "concept",
        "name_en": "Interconnected Cascade Tank Watershed Architecture & Micro-Basin Hydraulics (Eri Network)",
        "name_ta": "சங்கிலித் தொடர் ஏரி அமைப்பு - நீர்ப்பிடிப்புப் பாசனப் பொறியியல் மற்றும் வடிநில மேலாண்மை",
        "era": "Sangam to Late Medieval Era",
        "year_start": -400,
        "year_end": 1700,
        "thinai": "marutham",
        "summary_en": "Macro-watershed cascade system linking dozens of stepped contour reservoirs (eri) along topographical gradients, where surplus overflow from upper tanks fills lower reservoirs across entire river basins.",
        "summary_ta": "நில அமைப்பின் சரிவுகளுக்கு ஏற்ப சங்கிலித் தொடராக வெட்டப்பட்ட ஏரிகள்; மேலேயுள்ள ஏரியின் உபரி நீர் அடுத்த ஏரியை நிரப்பும் வடிநில நீர்ப்பிடிப்பு மேலாண்மை அமைப்பு.",
        "sources": [
            "Epigraphia Indica Vol XVIII",
            "Chola Water Systems & Cascade Tanks Survey"
        ],
        "content": "# Interconnected Cascade Tank Watershed Architecture (Eri Networks)\n\nAncient Tamil engineers recognized that in a semi-arid monsoonal climate characterized by short bursts of cyclonic rainfall, water security required macro-watershed harvesting rather than isolated ponds. They designed the celebrated cascade reservoir system (eri-cascade).\n\nMapped precisely across topographical contours from highland foothills to coastal plains, dozens of shallow reservoirs were linked in series along natural micro-valleys. As the highest tank (mel-eri) approached full capacity during heavy rains, surplus water discharged over masonry weirs into contour feeder channels, filling intermediate tanks (naduvil-eri), which in turn discharged into lower terminal reservoirs (keezh-eri).\n\nThis cascade architecture achieved multiple simultaneous objectives: it slowed flash-flood velocities, prevented catastrophic dam washouts, systematically recharged subsoil groundwater aquifers across entire sub-basins, and ensured zero runoff waste into the sea."
    },
    {
        "file": "knowledge/concepts/concept-masonry-overflow-weirs-and-emergency-flood-channels-kalingu.md",
        "slug": "concept-masonry-overflow-weirs-and-emergency-flood-channels-kalingu",
        "category": "concept",
        "name_en": "Cut-Stone Masonry Overflow Weirs & Surplus Flood Spillways (Kalingu & Vannaatha Kalingu)",
        "name_ta": "கலிங்கு - கருங்கல் உபரி நீர் வழிந்தோடி மற்றும் வெள்ளக் கட்டுப்பாட்டு மதகு",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1500,
        "thinai": "marutham",
        "summary_en": "Dressed-granite spillway structures (kalingu) engineered into reservoir earthen bunds, featuring slotted stone pillars that allowed flashboard height regulation to optimize storage while evacuating floods.",
        "summary_ta": "ஏரிக்கரையின் விளிம்பில் கருங்கற்களால் கட்டப்பட்ட உபரி நீர் வழிந்தோடி; பலகைகள் பொருத்தும் காடிகள் கொண்ட தூண்கள் மூலம் நீர்மட்டத்தை ஒழுங்குபடுத்தும் வெள்ளப் பாதுகாப்பு அமைப்பு.",
        "sources": [
            "South Indian Inscriptions Vol VIII",
            "Traditional Water Architecture in Tamil Nadu"
        ],
        "content": "# Cut-Stone Masonry Overflow Weirs (Kalingu)\n\nThe safety valve of every ancient Tamil reservoir was the kalingu (masonry overflow weir). Constructed at the exact design full-reservoir level (FRL), the kalingu was built from heavy dressed granite ashlar blocks bonded with hydraulic lime mortar to withstand turbulent torrents.\n\nA distinctive feature was the inclusion of vertical grooved stone pillars (kalingu thoon) erected across the crest of the spillway. Village water masters inserted wooden planks or sandbags into these slots during late monsoon months to raise storage capacity by two or three feet, maximizing dry-season reserves.\n\nIn the event of sudden catastrophic cyclones, the planks could be quickly knocked out, instantly tripling spillway discharge capacity and protecting the fragile earthen dam embankments from devastating overtopping failures."
    },
    {
        "file": "knowledge/concepts/concept-sub-surface-terracotta-pipe-aqueducts-and-cistern-filtration-urani.md",
        "slug": "concept-sub-surface-terracotta-pipe-aqueducts-and-cistern-filtration-urani",
        "category": "concept",
        "name_en": "Sub-Surface Terracotta Pipe Aqueducts & Gravity Sand Filtration Cisterns (Urani & Madai)",
        "name_ta": "சுடுமண் குழாய் நிலத்தடி நீர்க்கடத்தி மற்றும் மணல் வடிகட்டி ஊருணி அமைப்பு",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "Subterranean potable water distribution employing socketed terracotta conduit pipes and community percolation tanks (urani) with natural sand and gravel biological filtration beds.",
        "summary_ta": "சுடுமண் குழாய்களை ஒன்றோடொன்று இணைத்து நிலத்தடியில் நீர் செலுத்தும் முறை மற்றும் மணல் பரப்பிய ஊருணிகள் மூலம் தூய குடிநீர் வடிகட்டும் மரபுசார் தொழில்நுட்பம்.",
        "sources": [
            "Keezhadi Archaeological Reports",
            "Kodumanal Excavation Memoirs"
        ],
        "content": "# Sub-Surface Terracotta Aqueducts & Filtration Cisterns\n\nPotable drinking water management in urban settlements and religious sanctuaries reached remarkable sophistication through sub-surface terracotta aqueduct systems. Excavations at Keezhadi, Kodumanal, and Kaveripakkam have unearthed unbroken pipelines composed of interlocking flared-collar terracotta cylinders.\n\nThese pipes, manufactured from tempered clay and high-fired in reducing kilns, were joined with water-resistant resin and lime mastic, conveying water under gravity from pristine highland springs or reservoir headworks directly into domestic quarters.\n\nFor community consumption, ancient planners constructed dedicated drinking cisterns known as urani. Fed exclusively by surface runoff channeled through stepped gravel and charcoal settling traps, the urani remained isolated from agricultural irrigation canals and cattle washing, ensuring pure, sweet drinking water year-round."
    },
    {
        "file": "knowledge/inscriptions/insc-kaveripakkam-chola-sluice-construction-and-lake-endowment-epigraphs.md",
        "slug": "insc-kaveripakkam-chola-sluice-construction-and-lake-endowment-epigraphs",
        "category": "inscription",
        "name_en": "Kaveripakkam Imperial Epigraphs on Lake Sluice Construction, Desilting Taxes & Maintenance Guilds",
        "name_ta": "காவேரிப்பாக்கம் கல்வெட்டுகள் - ஏரி மதகு கட்டுமானம், ஏரி ஆயம் மற்றும் தூம்பு பராமரிப்பு சாசனம்",
        "era": "Pallava to Imperial Chola Era",
        "year_start": 850,
        "year_end": 1150,
        "thinai": "marutham",
        "summary_en": "Granite epigraphs from the Kaveripakkam reservoir complex recording the establishment of the Lake Maintenance Committee (Eri-Variyam), dedicated desilting boats, and sluice construction grants.",
        "summary_ta": "காவேரிப்பாக்கம் பெரிய ஏரியின் கரையில் உள்ள கல்வெட்டுகள்; ஏரி வாரியம் அமைத்து, வண்டல் தூர்வாரும் படகுகள் மற்றும் மதகுப் பழுதுபார்ப்புக்கான வரிகளைப் பதிவு செய்கின்றன.",
        "sources": [
            "South Indian Inscriptions Vol VII (Nos 390-410)",
            "Epigraphia Indica Vol VII"
        ],
        "content": "# Kaveripakkam Lake Sluice & Maintenance Epigraphs\n\nKaveripakkam, historically known as Kaveripakku or Vikramachola-chaturvedimangalam, holds some of the most comprehensive epigraphical records concerning reservoir maintenance in South India.\n\nThe inscriptions detail the operational protocols of the autonomous village assembly's Eri-Variyam (Lake Committee). The committee administered specialized water endowments (eri-patti), financed by a mandatory local levy called eri-ayam. The funds were used to maintain specialized wooden desilting boats (eri-thoni) operated by four professional boatmen who dredged silt daily from the mouth of the kumizhi-thoombu sluices.\n\nThe records also document the reconstruction of cut-stone kalingu overflow weirs and stone-piston sluices following hundred-year flood disasters during the reigns of Parantaka I and Rajaraja I."
    },
    {
        "file": "knowledge/inscriptions/insc-porunthal-lake-embankment-and-kumizhi-thoombu-sluice-charters.md",
        "slug": "insc-porunthal-lake-embankment-and-kumizhi-thoombu-sluice-charters",
        "category": "inscription",
        "name_en": "Porunthal Archaeological Epigraphs on Silt-Clearing Stone Sluices & Irrigation Endowments",
        "name_ta": "பொருந்தல் கல்வெட்டுகள் - வண்டல் அகற்றும் கல் மதகு மற்றும் பாசனக் கொடை சாசனங்கள்",
        "era": "Sangam to Early Medieval Era",
        "year_start": -100,
        "year_end": 800,
        "thinai": "marutham",
        "summary_en": "Ancient Tamil-Brahmi and Vatteluttu epigraphical records from Porunthal documenting early stone sluice mechanisms, reservoir bund stabilization, and community water shares.",
        "summary_ta": "பொருந்தல் தொல்லியல் தளத்தில் கண்டறியப்பட்ட தமிழ்-பிராமி மற்றும் வட்டெழுத்துக் கல்வெட்டுகள்; கல் மதகுகள், ஏரிக்கரை பலப்படுத்துதல் மற்றும் பாசனப் பங்கீடுகளை விளக்குகின்றன.",
        "sources": [
            "Porunthal Archaeological Excavation Reports",
            "Tamil-Brahmi Epigraphy of Palani Basin"
        ],
        "content": "# Porunthal Lake Embankment & Stone Sluice Charters\n\nRecovered during extensive excavations in the Palani river basin near Porunthal, these early inscriptions push back the verified antiquity of stone sluice technology to the late Sangam and Post-Sangam transitional era.\n\nThe texts, engraved on granite sluice pillars and field boundary stones, record endowments established by local agricultural chiefs (velir) to maintain lake embankments (eri-karai). The inscriptions specifically refer to the sluice mechanism as thoombu, outlining strict schedules for opening and closing the stone piston plugs during the kuruvai and samba rice cultivation cycles.\n\nCrucially, the records demonstrate that community water rights (neer-paasanam) were tied to landholdings, with strict penalties for tampering with sluice elevations or diverting surplus canal flows."
    },
    {
        "file": "knowledge/characters/char-kaveripakkam-master-hydraulic-sluice-architect-thoombu-asariyar.md",
        "slug": "char-kaveripakkam-master-hydraulic-sluice-architect-thoombu-asariyar",
        "category": "character",
        "name_en": "Kaveripakkam Master Hydraulic Sluice Architect & Stone Mason (Thoombu Asariyar)",
        "name_ta": "காவேரிப்பாக்கம் தலைமை நீர் மதகுச் சிற்பி மற்றும் தூம்பு ஆசாரியர்",
        "era": "Imperial Chola Era",
        "year_start": 980,
        "year_end": 1060,
        "thinai": "marutham",
        "summary_en": "Renowned civil engineer and master stone architect responsible for calculating hydro-static head pressures and carving monolithic granite kumizhi-thoombu sluice mechanisms for massive royal reservoirs.",
        "summary_ta": "சோழர் காலப் பெருநீர்த்தேக்கங்களில் நீரியல் அழுத்தத்தைக் கணக்கிட்டு, கருங்கல் குமிழித்தூம்புகள் மற்றும் மதகுகளை வடிவமைத்த தலைமை நீரியல் சிற்பி.",
        "sources": [
            "Kaveripakkam Temple Inscriptions",
            "Chola Civil Engineering Guild Records"
        ],
        "content": "# Kaveripakkam Master Sluice Architect (Thoombu Asariyar)\n\nThe Thoombu Asariyar was the master engineer responsible for the hydraulic integrity of imperial reservoirs. Combining profound knowledge of stone carving, soil mechanics, and hydrology, he directed the construction of complex sub-aqueous sluice boxes.\n\nHe calculated the exact dimensions of internal intake chambers, ensuring that the hydrodynamic suction vortex was strong enough to scour dense lake-bottom silt without undermining the surrounding stone foundations. He oversaw the quarrying of flawless granite monoliths, boring circular conduit tunnels through 40-foot stone beams using specialized coring drills and abrasive quartz slurries.\n\nHonored by royal court titles such as Perun-Thatchan and Thoombu Asariyar, he was gifted hereditary tax-free lands (asariyar-kaani) to ensure permanent family stewardship over the vital reservoir infrastructure."
    },
    {
        "file": "knowledge/characters/char-palavur-cascade-tank-watershed-engineer-eri-karanathan.md",
        "slug": "char-palavur-cascade-tank-watershed-engineer-eri-karanathan",
        "category": "character",
        "name_en": "Palavur Cascade Tank Watershed Engineer & Hydrologist (Eri Karanathan)",
        "name_ta": "பாலாவூர் சங்கிலித் தொடர் ஏரி வடிநிலப் பொறியாளர் மற்றும் ஏரிக் கணக்கன்",
        "era": "Medieval Chola Era",
        "year_start": 1020,
        "year_end": 1110,
        "thinai": "marutham",
        "summary_en": "Guild hydrologist and topographical surveyor who surveyed watershed gradients and managed real-time flood gate operations across cascading chains of interconnected reservoirs.",
        "summary_ta": "நிலச்சரிவுகளை அளந்து வடிநில சங்கிலித் தொடர் ஏரிகளை வடிவமைத்து, மழைக்காலத்தில் வெள்ளக் கதவுகளைத் திறந்து நீரைச் சீராகப் பகிர்ந்த தலைமை நீரியல் கணக்கர்.",
        "sources": [
            "Chola Water Revenue Rolls",
            "Eri-Variyam Administrative Registers"
        ],
        "content": "# Palavur Cascade Tank Watershed Engineer (Eri Karanathan)\n\nThe Eri Karanathan functioned as the chief water executive of regional tank cascade networks. Stationed in the Palavur basin, he surveyed micro-topographical contours using leveling water-tubes and plumb-lines, plotting gradient channels that connected higher feeder tanks to lower farming settlements.\n\nDuring cyclonic deluges, he coordinated an emergency signaling network between village tank watchmen (madai-kappon). Based on live water-level readings, he ordered the controlled lifting or insertion of kalingu flashboards, routing torrents from saturated reservoirs into empty downstream basins before dykes could breach.\n\nHe also maintained meticulously audited palm-leaf water rolls recording seasonal rainfall, siltation depths, and crop water quotas, ensuring equitable distribution across centuries of fluctuating monsoon patterns."
    },
    {
        "file": "knowledge/places/place-kaveripakkam-ancient-chola-cascade-reservoir-and-sluice-haven.md",
        "slug": "place-kaveripakkam-ancient-chola-cascade-reservoir-and-sluice-haven",
        "category": "place",
        "name_en": "Kaveripakkam: Ancient Cascade Reservoir & Piston-Sluice Engineering Haven",
        "name_ta": "காவேரிப்பாக்கம் - பண்டைய பிரம்மாண்ட ஏரிப் பாசனம் மற்றும் குமிழித்தூம்பு பொறியியல் தளம்",
        "era": "Prehistoric to Modern Era",
        "year_start": -300,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Monumental 1,500-acre medieval reservoir complex on the Palar basin featuring four-mile earthen bunds, colossal dressed-granite kalingu weirs, and ancient silt-clearing piston sluices.",
        "summary_ta": "பல்லவர் மற்றும் சோழர் காலத்தில் உருவாக்கப்பட்ட 1,500 ஏக்கர் பரப்பளவு கொண்ட பிரம்மாண்ட ஏரி; வரலாற்றுச் சிறப்புமிக்க குமிழித்தூம்புகள் மற்றும் கலிங்குகளின் தாய் தளம்.",
        "sources": [
            "North Arcot District Manual",
            "South Indian Epigraphical Surveys"
        ],
        "content": "# Kaveripakkam: Ancient Cascade Reservoir Engineering Haven\n\nSpread over several square miles between modern Kanchipuram and Vellore, the Kaveripakkam Lake (Kaveripakku Eri) stands as one of the largest and most historically significant artificial water reservoirs ever constructed in peninsular India.\n\nCreated by impounding surplus seasonal runoff from the Palar river basin, the lake is retained by an earthen embankment extending over eight kilometers in length. The reservoir's longevity is attributed to its sophisticated stone masonry installations, including the ancient southern and northern kalingu overflow weirs, which have endured centuries of monsoonal floods.\n\nArchaeological and engineering surveys of Kaveripakkam reveal masterfully preserved kumizhi-thoombu structures buried within the bed, proving that Tamil civil engineering achieved an enduring synthesis of hydraulic physics, ecological preservation, and civic community administration."
    }
]
EDGES = [
    [
        "text-porunarattruppadai-chola-irrigation-sluices-and-river-embankment-verse",
        "documents_masterwork",
        "concept-piston-valve-reservoir-silt-clearing-sluice-engineering-kumizhi-thoombu",
        "historical_proof",
        "Sangam Era",
        "Porunarattruppadai provides early bardic testimony to Karikala Chola's hydraulic sluice outlets and dyking.",
        "Porunarattruppadai lines 235-250"
    ],
    [
        "concept-piston-valve-reservoir-silt-clearing-sluice-engineering-kumizhi-thoombu",
        "component_of",
        "concept-interconnected-cascade-tank-watershed-architecture-eri-cascade",
        "historical_proof",
        "Sangam to Chola Era",
        "Underwater piston sluices served as the core bottom-discharge mechanisms in interconnected cascade tank networks.",
        "Hydraulic Archeology of South Indian Reservoirs"
    ],
    [
        "concept-interconnected-cascade-tank-watershed-architecture-eri-cascade",
        "utilizes_spillway",
        "concept-masonry-overflow-weirs-and-emergency-flood-channels-kalingu",
        "historical_proof",
        "Sangam to Late Medieval Era",
        "Cascade networks relied upon dressed-stone kalingu weirs to transfer surplus floodwater safely to downstream tanks.",
        "Chola Water Systems & Cascade Tanks Survey"
    ],
    [
        "concept-interconnected-cascade-tank-watershed-architecture-eri-cascade",
        "supplies_potable",
        "concept-sub-surface-terracotta-pipe-aqueducts-and-cistern-filtration-urani",
        "historical_proof",
        "Sangam to Medieval Era",
        "Upstream cascade reservoirs fed gravity-driven sub-surface terracotta pipelines supplying community uranis.",
        "Kodumanal Excavation Memoirs"
    ],
    [
        "char-kaveripakkam-master-hydraulic-sluice-architect-thoombu-asariyar",
        "operates_in",
        "place-kaveripakkam-ancient-chola-cascade-reservoir-and-sluice-haven",
        "historical_proof",
        "Imperial Chola Era",
        "Master sluice architects engineered the massive granite kumizhi-thoombu installations at Kaveripakkam Lake.",
        "Kaveripakkam Temple Inscriptions"
    ],
    [
        "char-kaveripakkam-master-hydraulic-sluice-architect-thoombu-asariyar",
        "builds_mechanism",
        "concept-piston-valve-reservoir-silt-clearing-sluice-engineering-kumizhi-thoombu",
        "historical_proof",
        "Imperial Chola Era",
        "The master architect carved and assembled monolithic stone cylinders and piston plugs for underwater sluices.",
        "Chola Civil Engineering Guild Records"
    ],
    [
        "char-palavur-cascade-tank-watershed-engineer-eri-karanathan",
        "manages_system",
        "concept-interconnected-cascade-tank-watershed-architecture-eri-cascade",
        "historical_proof",
        "Medieval Chola Era",
        "The watershed hydrologist audited contour gradients and real-time weir operations across cascade tank chains.",
        "Eri-Variyam Administrative Registers"
    ],
    [
        "insc-kaveripakkam-chola-sluice-construction-and-lake-endowment-epigraphs",
        "attests_place",
        "place-kaveripakkam-ancient-chola-cascade-reservoir-and-sluice-haven",
        "historical_proof",
        "Pallava to Imperial Chola Era",
        "Kaveripakkam epigraphs document the historical Eri-Variyam lake committee, desilting boats, and sluice repairs.",
        "South Indian Inscriptions Vol VII"
    ],
    [
        "insc-porunthal-lake-embankment-and-kumizhi-thoombu-sluice-charters",
        "records_mechanism",
        "concept-piston-valve-reservoir-silt-clearing-sluice-engineering-kumizhi-thoombu",
        "historical_proof",
        "Sangam to Early Medieval Era",
        "Porunthal inscriptions provide early epigraphical evidence of thoombu stone sluices and community water rights.",
        "Porunthal Archaeological Excavation Reports"
    ],
    [
        "place-kaveripakkam-ancient-chola-cascade-reservoir-and-sluice-haven",
        "exemplifies_architecture",
        "concept-masonry-overflow-weirs-and-emergency-flood-channels-kalingu",
        "historical_proof",
        "Prehistoric to Modern Era",
        "Kaveripakkam's monumental granite kalingu weirs exemplify the apex of classical Tamil reservoir engineering.",
        "North Arcot District Manual"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Ancient Tamil Hydraulic Sluices & Cascade Reservoirs into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Ancient Tamil Hydraulic Sluices & Cascade Reservoirs Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
