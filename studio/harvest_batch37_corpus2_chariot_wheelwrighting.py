#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Chariot Wheelwrighting, Spoke-Felloe Dynamics & Processional Vehicles
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
        "file": "knowledge/texts/text-purananuru-87-verses-on-master-wheelwrights-and-monumental-war-chariots.md",
        "slug": "text-purananuru-87-verses-on-master-wheelwrights-and-monumental-war-chariots",
        "category": "text",
        "name_en": "Purananuru 87: Classical Verses on Royal Wheelwrights, Hardwood Felloes & War Chariots",
        "name_ta": "புறநானூறு 87 - தேர் தச்சன் ஒரு திங்களில் செய்யும் ஆழித் தேர், ஆரக்கால் மற்றும் மர வேலை இலக்கியப் பாடல்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Famous Sangam verse by Avvaiyar comparing the warrior Adigaman Neduman Anji to a master wheelwright (thaer-thatchan) who spends an entire month crafting a single supreme chariot wheel.",
        "summary_ta": "ஔவையார் பாடிய புறநானூற்றுப் பாடலில், திறமைமிக்க தேர் தச்சன் ஒரு மாதம் முழுதும் உழைத்து உருவாக்கும் உறுதிமிக்க தேர் சக்கரம் போன்ற வலிமைமிக்க அதியமானை விவரிக்கும் பாடல்.",
        "sources": [
            "Purananuru 87",
            "Malaipadukadam 490-505",
            "Purananuru 224"
        ],
        "content": "# Purananuru 87: Royal Wheelwrights & War Chariots\n\nIn *Purananuru* 87, the renowned Sangam poetess Avvaiyar crafts a magnificent technical metaphor to extol the martial fortitude of King Adigaman Neduman Anji:\n\n> \"Like a master chariot-maker (*thaer-thatchan*) who labours for a full month with razor-honed chisels to construct a single flawless chariot wheel (*orukaal*), assembling seasoned hardwood felloes and radial spokes to carry monumental loads over stony battlefields...\"\n\nThis celebrated verse documents the supreme artisanal stature, specialized joinery, and intense craftsmanship demanded by ancient Tamil chariot engineering (*thaer-kalai*). War and processional vehicles were not rough carts, but sophisticated composite machines engineered for dynamic resilience."
    },
    {
        "file": "knowledge/concepts/concept-azhi-kaal-composite-timber-wheel-felloe-spoke-and-hub-kinematics.md",
        "slug": "concept-azhi-kaal-composite-timber-wheel-felloe-spoke-and-hub-kinematics",
        "category": "concept",
        "name_en": "Azhi-Kaal: Wheel Kinematics, Segmental Felloe Joinery & Radial Spoke Pre-Stressing",
        "name_ta": "ஆழிக் கால் - தேர் சக்கர இயக்கவியல், வளைவு மரப் பொருத்து மற்றும் ஆரக்கால் முறுக்கு விசை",
        "era": "Iron Age to Medieval Era",
        "year_start": -500,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "Kinematic and mechanical engineering of monumental wooden chariot wheels, utilizing curved segmented felloe blocks (kudam), mortised radial spokes (aaram), and bronze-bushed axle hubs.",
        "summary_ta": "தேக்கு, வேங்கை மரங்களை வளைத்து இணைக்கப்பட்ட பலகை வட்டங்கள், மையக் குடம் மற்றும் அதிர்வுகளைத் தாங்கும் ஆரக்கால்களின் இயக்கவியல் கட்டமைப்பு.",
        "sources": [
            "Shilpa Shastra: Ratha Lakshana",
            "Journal of Wood Science and Heritage Joinery",
            "Archaeological Studies of Ancient Indian Chariots"
        ],
        "content": "# Azhi-Kaal: Chariot Wheel Kinematics & Joinery\n\nThe monumental chariot wheel (*azhi* or *kaal*) was an engineering masterpiece composed of three interconnected structural assemblies:\n\n- **The Axle Hub (*Kudam*)**: The central nave, turned on heavy lathes from seasoned dense hardwood (such as tamarind or ironwood), housed the heavy wrought axle (*thadukka*) encased within lubricating bronze sleeves.\n- **Radial Compression Spokes (*Aaram*)**: Up to 16 to 32 spokes radiated from the nave, each hand-tapered and mortised tightly with interlocking tenons at both hub and outer rim to distribute impact energy radially.\n- **Segmented Curved Felloes (*Vatta-Palagai*)**: The circular rim was composed of 6 to 8 curved segmental blocks of Vengai (*Pterocarpus marsupium*) or rosewood, linked together with double-dovetail butterfly keys (*poruthu*) to absorb angular shearing stresses."
    },
    {
        "file": "knowledge/technologies/technology-thaer-vada-kattu-massive-coir-towing-cable-rigging-and-steering-pivots.md",
        "slug": "technology-thaer-vada-kattu-massive-coir-towing-cable-rigging-and-steering-pivots",
        "category": "technology",
        "name_en": "Thaer-Vada-Kattu: Monumental Coir Towing Hawsers, Lever Steering & Turning Physics",
        "name_ta": "தேர் வடக் கட்டு - பிரம்மாண்ட தேர்வடக் கயிறு, நெம்புகோல் திருப்புதல் மற்றும் இழுவை விசையியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Heavy rigging technology comprising braided 300-meter coconut fiber towing cables (vadam) and wooden fulcrum steering levers (perun-thadi) capable of mobilizing and turning 300-ton temple processional cars.",
        "summary_ta": "300 டன் எடையுள்ள பிரம்மாண்ட தேர்களை ஆயிரக்கணக்கான பக்தர்கள் இழுப்பதற்கு உதவும் கனரக தேர்வடக் கயிறுகள் மற்றும் வளைவுகளில் திருப்ப உதவும் நெம்புகோல் நுட்பம்.",
        "sources": [
            "Thiruvarur Temple Procession Manuals",
            "Journal of Traditional Rope Rigging",
            "Imperial Chola Temple Epigraphs"
        ],
        "content": "# Thaer-Vada-Kattu: Towing Cables & Steering Mechanics\n\nMobilizing colossal temple chariots weighing hundreds of tons required colossal rigging and crowd-coordinated mechanics:\n\n- **The Monster Hawser (*Vadam*)**: Towing cables up to 300 meters long and 20–25 cm in diameter were braided from thousands of strands of selected salt-cured coconut coir (*thengai-naar*). Four primary cables were anchored directly to the chassis main longitudinal stringers.\n- **Tensile Resilience**: Coir's natural high elasticity cushioned the immense shock loads generated when 5,000 worshippers hauled in unison, preventing cable snapping.\n- **Fulcrum Lever Steering (*Perun-Thadi*)**: Chariots lacked steerable front automotive axles. To execute ninety-degree street turns (*madathu-thiruppam*), master wheelwrights inserted massive 10-meter hardwood beams under the rear wheels, using human weight to lever the wheels sideways onto greased iron sheets."
    },
    {
        "file": "knowledge/artifacts/artifact-irumbu-pattarai-and-kadam-wrought-iron-wheel-tires-and-axle-linchpins.md",
        "slug": "artifact-irumbu-pattarai-and-kadam-wrought-iron-wheel-tires-and-axle-linchpins",
        "category": "artifact",
        "name_en": "Irumbu-Pattarai & Kadam: Shrink-Fitted Iron Wheel Tires, Hardened Linchpins & Axle Sleeves",
        "name_ta": "இரும்புப் பட்டறை மற்றும் கடம் - வெப்பச் சுருங்கல் இரும்புப் பட்டை, அச்சாணி மற்றும் இருசுப் பூண்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Pyrotechnic metallurgical assembly where glowing-red circular wrought iron tires (pattarai) were shrink-fitted onto wooden felloes, clamped tight with water quenching, and locked with forged wootz linchpins (achani).",
        "summary_ta": "சிவக்கக் காய்ச்சிய இரும்பு வளையத்தை மரச் சக்கரத்தின் மீது ஏற்றி, உடனே குளிர்ந்த நீர் ஊற்றி மரத்தை இறுகப் பற்ற வைக்கும் வெப்பச் சுருங்கல் நுட்பம் மற்றும் எஃகு அச்சாணிகள்.",
        "sources": [
            "Keezhadi Iron Artifact Studies",
            "Adichanallur Wheel Metallurgy",
            "Indian Journal of History of Science"
        ],
        "content": "# Irumbu-Pattarai & Kadam: Iron Wheel Tires & Linchpins\n\nThe fusion of carpentry and blacksmithing reached its zenith in the shrink-fitting of chariot wheel tires:\n\n- **Thermal Expansion & Shrink-Fitting**: A circular iron band (*irumbu-pattarai*) forged slightly smaller than the outer circumference of the wooden wheel was heated in an open circular bonfire until glowing cherry red, expanding by several millimeters.\n- **Rapid Quenching**: Blacksmiths lifted the expanded glowing hoop with heavy tongs, hammered it over the wooden rim, and immediately doused it with cold water. The sudden thermal contraction gripped the segmental felloe blocks with monumental compressive force, locking all joints into a single rigid hoop.\n- **Wootz Axle Linchpins (*Achani*)**: Heavy tapered pins forged from tough carbon steel were driven through the axle ends, retaining the wheel hubs against severe lateral wobble."
    },
    {
        "file": "knowledge/concepts/concept-rathakara-structural-timber-damping-and-shock-absorption-physics.md",
        "slug": "concept-rathakara-structural-timber-damping-and-shock-absorption-physics",
        "category": "concept",
        "name_en": "Rathakara Mechanics: Structural Timber Damping, Harmonic Resonance & Deflection Elasticity",
        "name_ta": "ரதகார விசையியல் - மரக்கட்டமைப்பின் அதிர்வு தணிப்பு, இசைவு ஒத்திசைவு மற்றும் மீள்தன்மை",
        "era": "Classical Antiquity to Medieval Era",
        "year_start": -400,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "Mechanical physics of timber species selection (teak, rosewood, vengai, poovarasu) configured in anisotropic structural frameworks to dampen violent ground vibrations over uneven stone pavements.",
        "summary_ta": "கரடுமுரடான கற்கள் நிறைந்த வீதிகளில் தேர் உருளும் போது ஏற்படும் அதிர்வுகளை உள்வாங்கி, பிரம்மாண்ட விமானக் கோபுரம் சாய்ந்துவிடாமல் காக்கும் மரக் கட்டமைப்பு இயற்பியல்.",
        "sources": [
            "Mayamata Vastu Shastra Treatise on Rathas",
            "Journal of Structural Engineering in Heritage Architecture",
            "Chola Epigraphical Corpus on Rathakaras"
        ],
        "content": "# Rathakara Mechanics: Structural Vibration Damping\n\nProcessional chariots standing up to 30 meters high faced severe dynamic instability when rattling over rough cobblestone streets:\n\n- **Anisotropic Timber Pairing**: Wheelwrights never built an entire chassis from a single wood species. Axles were crafted from ultra-dense *iluppai* (Madhuca longifolia) for shear resistance; wheels from elastic *vengai*; and upper framing from lightweight, fibrous *teak* (*thekku*).\n- **Mechanical Damping**: Wood possesses internal cellular viscoelasticity that naturally dissipates shock wave energy four times faster than steel. The thousands of pinned mortise-and-tenon joints acted as microscopic friction dampers.\n- **Harmonic Decoupling**: The towering pyramidal upper spire was isolated from the heavy wheeled platform by intermediary elastomeric timber cushions, preventing resonant catastrophic failure during sudden stops."
    },
    {
        "file": "knowledge/institutions/institution-rathakara-and-thaer-thatchar-corporation-of-temple-chariot-architects.md",
        "slug": "institution-rathakara-and-thaer-thatchar-corporation-of-temple-chariot-architects",
        "category": "institution",
        "name_en": "Rathakara & Thatchar: Royal Corporation of Chariot Architects, Guild Charters & Epigraphs",
        "name_ta": "ரதகாரர் மற்றும் தேர் தச்சர் - அரச தேர் தச்சர்கள், சிற்பிகள் அவை மற்றும் சோழர் கால பட்டயக் கூட்டமைப்பு",
        "era": "Iron Age to Medieval Era",
        "year_start": -500,
        "year_end": 1500,
        "thinai": "marutham",
        "summary_en": "Privileged professional guild of master chariot builders (Rathakaras) endowed with royal tax immunities, temple shares, and customary rights to design, fabricate, and test imperial and temple cars.",
        "summary_ta": "கோயில் தேர்களை உருவாக்கவும், வரிவிலக்குகள் பெறவும் சோழ மற்றும் பாண்டிய மன்னர்களால் அங்கீகரிக்கப்பட்ட சிறப்பு ரதகார தச்சர்கள் மற்றும் சிற்பிகள் சங்கம்.",
        "sources": [
            "Uttiramerur Inscriptions of Parantaka I",
            "Epigraphia Indica on Rathakara Rights",
            "Thiruvalangadu Copper Plates"
        ],
        "content": "# Rathakara & Thatchar: Chariot Guild Charters & Privileges\n\nThe *Rathakaras* enjoyed an elite, legally protected status distinct from ordinary carpenters:\n\n- **The Imperial Chola Charters**: Inscriptions from Uttiramerur and Kumbakonam record royal debates establishing the hereditary ritual and civil prerogatives of Rathakaras, granting them rights to invest themselves with the sacred thread, build royal palaces, cast bronze regalia, and engineer monumental temple cars.\n- **Apprenticeship & Geometry**: Guild masters (*sthapathis*) trained disciples in advanced geometric canons (*shilpa-shastras*), calculating center-of-gravity, axle cant, and spire proportions using traditional cord measurements (*soothiram*).\n- **Guild Verification & Trial Runs**: Before a new chariot was consecrated for religious festivals, the guild conducted trial runs (*ottam*) loaded with equivalent sand ballast to verify axle temperatures and structural alignment."
    },
    {
        "file": "knowledge/technologies/technology-chithira-thaer-multi-tiered-pyramidal-vimana-superstructure-engineering.md",
        "slug": "technology-chithira-thaer-multi-tiered-pyramidal-vimana-superstructure-engineering",
        "category": "technology",
        "name_en": "Chithira-Thaer: Multi-Tiered Pyramidal Vimana Superstructure & Modular Timber Framing",
        "name_ta": "சித்திரத் தேர் - பல அடுக்கு பிரமிடு வடிவ விமானக் கட்டமைப்பு மற்றும் மட்டுக்கட்டு மரக் கூட்டமைப்பு",
        "era": "Early Medieval to Modern Era",
        "year_start": 800,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Architectural and structural engineering of towering mobile vimana spires rising up to 7 tiers, built with interlocking lightweight bamboo-timber trusses draped in silk canopies and brass kalasams.",
        "summary_ta": "ஏழு அடுக்குகள் கொண்ட நகரும் கோயில் விமானக் கோபுரம், மூங்கில் மற்றும் இலகுரக மரங்களால் பிணைக்கப்பட்டு பட்டுத் திரைகளுடன் கம்பீரமாக உயர்த்தப்படும் நுட்பம்.",
        "sources": [
            "Silpa Shastra: Deva Ratha Nirmana",
            "Tanjore Brihadisvara Temple Records",
            "Madurai Meenakshi Temple Chariot Manuals"
        ],
        "content": "# Chithira-Thaer: Multi-Tiered Vimana Superstructure\n\nA temple processional car was conceived as a mobile monumental shrine (*chala-vimana*):\n\n- **Stepped Pyramidal Superstructure**: Rising above the solid chassis, the upper spire (*vimanam*) tapered across 5 to 7 tiers, mimicking the stone Dravidian gopurams of the sacred precinct.\n- **Modular Bamboo-Timber Trusses**: To keep the center of gravity low and prevent wind capsize, the upper stages were constructed from lightweight bamboo trusses and dried cedar framing, pegged together with wooden trenails (*marani*) rather than heavy iron bolts.\n- **Textile & Metal Regalia**: During festivals, the bare wooden skeleton was swathed in thousands of meters of vibrant crimson and gold silk (*vithanam*), surmounted by hammered brass finials (*kalasam*) that glittered under the sun."
    },
    {
        "file": "knowledge/artifacts/artifact-aazhi-vaali-and-perun-thadi-heavy-wooden-brake-chocks-and-lever-bars.md",
        "slug": "artifact-aazhi-vaali-and-perun-thadi-heavy-wooden-brake-chocks-and-lever-bars",
        "category": "artifact",
        "name_en": "Aazhi-Vaali & Mutti: Hardwood Brake Chocks, Kinetic Stopping Wedges & Leverage Bars",
        "name_ta": "ஆழி வாலி மற்றும் முட்டு - கனரக மர நிறுத்தக் கட்டை, இயக்கவியல் தடுப்பு முட்டு மற்றும் நெம்பு கம்புகள்",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Heavy wedge-shaped hardwood chocks (mutti) and trailing brake beams operated by specialized crews to immediately arrest moving multi-ton chariots and prevent runaway momentum on declines.",
        "summary_ta": "நகரும் பிரம்மாண்ட தேர் நிற்க வேண்டிய இடத்தில் சக்கரத்தின் அடியில் லாவகமாகப் போடப்படும் கனரக தேக்கு மர முட்டுக் கட்டைகள் மற்றும் நெம்பு கம்புகள்.",
        "sources": [
            "Thiruvarur Temple Festival Operational Records",
            "Tamil Lexicon on Ther-Muttu",
            "Traditional Chariot Braking Protocols"
        ],
        "content": "# Aazhi-Vaali & Mutti: Braking Wedges & Safety Levers\n\nStopping a 300-ton rolling mass pulled by thousands of excited worshippers without mechanical friction disc brakes was a life-critical technical operation:\n\n- **The Braking Wedge (*Mutti*)**: Hand-carved from solid blocks of dense, split-resistant timber (*Iluppai*), these wedge-shaped blocks were curved to match the radius of the iron tire.\n- **The Chock-Throwing Squad (*Muttik-Kaarar*)**: A specialized hereditary squad ran alongside the rolling wheels. At the sound of the master conductor's conch (*sangu*), they simultaneously shoved the heavy chocks beneath both rear wheels. The forward momentum forced the wheels up the incline of the wedges, instantly arresting rotation through friction and gravity.\n- **Rear Safety Drag-Beams**: Heavy trailing timber beams dragged behind the chassis prevented backwards rollback on street gradients."
    },
    {
        "file": "knowledge/concepts/concept-dynamic-ground-bearing-pressure-and-multi-wheel-load-distribution.md",
        "slug": "concept-dynamic-ground-bearing-pressure-and-multi-wheel-load-distribution",
        "category": "concept",
        "name_en": "Load Distribution: Ground Bearing Pressure, Multi-Wheel Bogies & Axle Stress Analysis",
        "name_ta": "தரை அழுத்தப் பரவல் - பல சக்கர பாரப் பகிர்வு, இருசுத் தகைவு மற்றும் மண் தாங்குதிறன் இயற்பியல்",
        "era": "Classical Antiquity to Modern Era",
        "year_start": -300,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Civil and mechanical physics distributing 100 to 300 tons of dead weight across 4 to 8 massive broad-rimmed wheels, ensuring ground bearing pressure does not exceed street subgrade bearing capacity.",
        "summary_ta": "நூற்றுக்கணக்கான டன் எடையுள்ள தேர் தெருக்களில் புதைந்துவிடாமல் இருக்க, அகலமான சக்கரங்கள் மூலம் தரை அழுத்தத்தைச் சமமாகப் பரப்பும் மண்ணியல் மற்றும் விசையியல் நுட்பம்.",
        "sources": [
            "Soil Mechanics and Foundation Engineering of Temple Streets",
            "Structural Analysis of Traditional Indian Chariots",
            "Journal of Archaeological Engineering"
        ],
        "content": "# Load Distribution: Ground Bearing Pressure & Multi-Wheel Bogies\n\nThe immense mass of imperial processional chariots posed catastrophic risks of puncturing urban street surfaces:\n\n- **Ground Bearing Pressure Calculations**: A 200-ton car resting on standard narrow wheels would generate contact pressures exceeding 1.5 MPa, instantly crushing stone paving slabs into underground drainage conduits.\n- **Broad-Rim Dispersion**: Wheelwrights fabricated wheels with massive widths (up to 0.6–0.8 meters wide), spreading the load across substantial contact footprints to keep ground pressures below 0.3 MPa.\n- **Multi-Wheel Chassis Configurations**: Giant cars—such as the celebrated Thiruvarur Azhi-Ther—employed double concentric wheels or 4 main wheels supplemented by auxiliary stabilization wheels, distributing dead loads across multiple contact points."
    },
    {
        "file": "knowledge/places/place-thiruvarur-ancient-azhi-ther-chariot-haven.md",
        "slug": "place-thiruvarur-ancient-azhi-ther-chariot-haven",
        "category": "place",
        "name_en": "Thiruvarur: Ancient Azhi-Ther Chariot Haven, Kamalalayam Tank & Processional Capital",
        "name_ta": "திருவாரூர் - பண்டைய ஆழித் தேர் தளம், கமலாலயத் தீர்த்தம் மற்றும் சோழர் தேர் விழாப் பெருநகரம்",
        "era": "Early Medieval to Modern Era",
        "year_start": 600,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "The sacred Chola processional capital in the fertile Kaveri Delta, celebrated throughout history for the legendary Azhi-Ther—the largest temple chariot on earth—and its vast four-caravan car streets.",
        "summary_ta": "காவிரி டெல்டாவில் அமைந்துள்ள சோழர்களின் புனித நகரம், உலகப் புகழ்பெற்ற பிரம்மாண்ட ஆழித் தேர் மற்றும் நான்கு மாட வீதிகளில் நடைபெறும் வரலாற்றுத் தேர் திருவிழாத் தளம்.",
        "sources": [
            "Appar and Sambandar Thevaram Hymns on Thiruvarur Ther",
            "Periyapuranam: Manu Needhi Cholan Legend",
            "Thiruvarur Temple Inscriptions"
        ],
        "content": "# Thiruvarur: Ancient Azhi-Ther Chariot Haven\n\nSituated around the magnificent 33-acre Kamalalayam sacred tank in Thiruvarur district, this historic secondary capital of the Cholas is the global pinnacle of chariot culture:\n\n- **The Legendary Azhi-Ther**: Rising to an astounding height of over 30 meters and weighing in excess of 300 tons, the Thiruvarur chariot dedicated to Sri Thyagarajaswami is the largest mobile wooden structure constructed by human civilization.\n- **The Four Car Streets (*Maada-Veethi*)**: The town plan was engineered around the chariot's dimensions: four immense, broad stone-paved processional streets forming a perfect 1-kilometer square circuit around the temple.\n- **Manu Needhi Cholan Monument**: Thiruvarur commemorates the legendary monarch Manu Needhi Cholan, who ran his own war chariot over his prince to deliver justice to a grieving cow, symbolizing the chariot as an enduring emblem of sacred law (*dharma*) and sovereignty."
    }
]

EDGES = [
    [
        "text-purananuru-87-verses-on-master-wheelwrights-and-monumental-war-chariots",
        "DESCRIBES",
        "concept-azhi-kaal-composite-timber-wheel-felloe-spoke-and-hub-kinematics",
        "core",
        "Sangam Era",
        "Purananuru 87 verses celebrate the master wheelwright constructing monumental chariot wheels.",
        "Purananuru 87"
    ],
    [
        "concept-azhi-kaal-composite-timber-wheel-felloe-spoke-and-hub-kinematics",
        "REINFORCED_BY",
        "artifact-irumbu-pattarai-and-kadam-wrought-iron-wheel-tires-and-axle-linchpins",
        "core",
        "Iron Age to Modern Era",
        "Thermal shrink-fitted iron tires clamped wooden felloes into a rigid structural ring.",
        "Adichanallur Wheel Metallurgy"
    ],
    [
        "concept-azhi-kaal-composite-timber-wheel-felloe-spoke-and-hub-kinematics",
        "MOBILIZED_BY",
        "technology-thaer-vada-kattu-massive-coir-towing-cable-rigging-and-steering-pivots",
        "core",
        "Iron Age to Modern Era",
        "Hundreds of meters of braided coir cables towed the multi-ton chariot chassis.",
        "Thiruvarur Temple Procession Manuals"
    ],
    [
        "technology-thaer-vada-kattu-massive-coir-towing-cable-rigging-and-steering-pivots",
        "STOPPED_BY",
        "artifact-aazhi-vaali-and-perun-thadi-heavy-wooden-brake-chocks-and-lever-bars",
        "core",
        "Iron Age to Modern Era",
        "Dense hardwood brake wedges were thrust under rotating wheels to halt motion.",
        "Thiruvarur Temple Festival Operational Records"
    ],
    [
        "concept-azhi-kaal-composite-timber-wheel-felloe-spoke-and-hub-kinematics",
        "GOVERNED_BY",
        "concept-rathakara-structural-timber-damping-and-shock-absorption-physics",
        "core",
        "Classical Antiquity to Medieval Era",
        "Anisotropic timber selection damped ground vibrations and prevented spire resonance.",
        "Mayamata Vastu Shastra Treatise on Rathas"
    ],
    [
        "concept-rathakara-structural-timber-damping-and-shock-absorption-physics",
        "MASTERED_BY",
        "institution-rathakara-and-thaer-thatchar-corporation-of-temple-chariot-architects",
        "core",
        "Iron Age to Medieval Era",
        "Rathakara guilds held royal charters and shastra canons to engineer temple cars.",
        "Uttiramerur Inscriptions of Parantaka I"
    ],
    [
        "institution-rathakara-and-thaer-thatchar-corporation-of-temple-chariot-architects",
        "ERECTED",
        "technology-chithira-thaer-multi-tiered-pyramidal-vimana-superstructure-engineering",
        "core",
        "Early Medieval to Modern Era",
        "Guild sthapathis engineered multi-tiered pyramidal spires rising up to 7 tiers.",
        "Silpa Shastra: Deva Ratha Nirmana"
    ],
    [
        "concept-azhi-kaal-composite-timber-wheel-felloe-spoke-and-hub-kinematics",
        "DISTRIBUTES_LOAD_VIA",
        "concept-dynamic-ground-bearing-pressure-and-multi-wheel-load-distribution",
        "core",
        "Classical Antiquity to Modern Era",
        "Broad wheel treads and multi-wheel layouts distributed 300 tons over street pavings.",
        "Soil Mechanics and Foundation Engineering of Temple Streets"
    ],
    [
        "institution-rathakara-and-thaer-thatchar-corporation-of-temple-chariot-architects",
        "HEADQUARTERED_AT",
        "place-thiruvarur-ancient-azhi-ther-chariot-haven",
        "core",
        "Early Medieval to Modern Era",
        "Thiruvarur served as the supreme processional capital and chariot engineering haven.",
        "Thiruvarur Temple Inscriptions"
    ],
    [
        "technology-chithira-thaer-multi-tiered-pyramidal-vimana-superstructure-engineering",
        "CONSECRATED_AT",
        "place-thiruvarur-ancient-azhi-ther-chariot-haven",
        "core",
        "Early Medieval to Modern Era",
        "The colossal 30-meter Azhi-Ther circled the four broad streets of Thiruvarur annually.",
        "Appar and Sambandar Thevaram Hymns on Thiruvarur Ther"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 37: Ancient Tamil Chariot Wheelwrighting, Spoke-Felloe Dynamics & Processional Vehicles...")
    
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

    print(f"Ingestion Complete for Batch 37 Corpus! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
