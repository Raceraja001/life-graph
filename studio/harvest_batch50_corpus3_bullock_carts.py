#!/usr/bin/env python3
"""
Harvester: Batch 50 - Ancient Tamil Bullock Cart Wheelwright Engineering, Shrink-Fit Iron Tyre Pyrotechnics, Axle Joinery & Peru-Vazhi Logistics
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

# The knowledge tree uses real English plurals ("technologies", not "technologys").
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
        "slug": "text-tirukkural-and-sangam-accounts-of-saagadam-achaani-and-umanar-salt-carts",
        "category": "text",
        "file": "text-tirukkural-and-sangam-accounts-of-saagadam-achaani-and-umanar-salt-carts.md",
        "name_en": "Tirukkural & Sangam Accounts of Saagadam Freight Carts, Achaani Linchpins & Umanar Caravans",
        "name_ta": "திருக்குறள் மற்றும் சங்க இலக்கியங்களில் சாகாடு, அச்சாணி மற்றும் உமணர் உப்பு வண்டி வாணிகம்",
        "era": "Sangam to Post-Sangam Era",
        "year_start": -300,
        "year_end": 500,
        "thinai": "mullai",
        "summary_en": "Classical Tamil literary attestations in Tirukkural (475 & 667), Perumpanarruppadai, Ahananuru, and Natrinai describing spoked freight carts (saagadam / chagadu / pandil), the structural criticality of the tiny axle linchpin (achaani), axle overload failure under peacock feathers, and Umanar salt-merchant cart caravans.",
        "summary_ta": "திருக்குறள் (475, 667), பெரும்பாணாற்றுப்படை, அகநானூறு மற்றும் நற்றிணையில் விவரிக்கப்படும் பண்டில், சாகாடு, உருள்பெருந்தேர்க்கு அச்சாணி உவமை மற்றும் உமணர்களின் உப்பு வண்டிப் பெருவழிப் பயணம்.",
        "sources": [
            "Tirukkural (Couplets 475 & 667)",
            "Perumpanarruppadai",
            "Ahananuru",
            "Natrinai",
            "Purananuru"
        ],
        "content": "# Tirukkural & Sangam Accounts of Saagadam Carts & Achaani Linchpins\n\nClassical Tamil poetry and ethical treatises preserve vivid engineering metaphors drawn from heavy overland bullock-cart (*saagadam* or *pandil*) transport:\n\n**Literary & Engineering Attestations:**\n- **Tirukkural on Axle Overload & Linchpins**: In Couplet 475 (*\"பீலிபெய் சாகாடும் அச்சிறும் அப்பண்டம் சால மிகுத்துப் பெயின்\"*), Valluvar observes that even a cart loaded with soft peacock feathers will snap its axle (*achu*) if piled beyond its flexural bending limit. In Couplet 667 (*\"உருவுகண்டு எள்ளாமை வேண்டும் உருள்பெருந்தேர்க்கு அச்சாணி அன்னார் உடைத்து\"*), he compares indispensable ministers to the tiny iron linchpin (*achaani*) that keeps the massive rolling wheel on its axle.\n- **Sangam Umanar Salt Caravans**: *Perumpanarruppadai* and *Ahananuru* describe long convoys of creaking spoked carts driven by *Umanar* salt merchants ascending stony mountain passes (*kavalai*) with spare axles (*semochu*) lashed beneath the chassis."
    },
    {
        "slug": "concept-large-diameter-spoked-wheel-rolling-resistance-and-dished-spoke-mechanics",
        "category": "concept",
        "file": "concept-large-diameter-spoked-wheel-rolling-resistance-and-dished-spoke-mechanics.md",
        "name_en": "Large-Diameter Spoked Wheel Terramechanics, Rolling Resistance & Conical Dished Spoke Geometry",
        "name_ta": "பெருவிட்ட ஆரக்கால் சக்கரத்தின் உருள் எதிர்ப்புக் குறைப்பும் சாய்வு ஆரக்கால் பொறியியலும்",
        "era": "Iron Age to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Terramechanics and structural wood science of the traditional Tamil bullock-cart wheel (kattai-vandi chakkaram, 1.5–1.8 m diameter): how large wheel radius minimizes sinkage and rolling resistance over loose sand and wet clay ruts, conical dished spoke geometry resisting lateral thrust, and differential timber selection (karuvelam vs vengai).",
        "summary_ta": "மணல் மற்றும் சேற்றுப் பாதைகளில் புதையாமல் உருள உதவும் 5–6 அடி உயர மரச் சக்கரத்தின் இயற்பியல், பக்கவாட்டு அதிர்வைத் தாங்கும் சாய்வு ஆரக்கால்கள் மற்றும் கருவேலம்-வேங்கை மரத் தேர்வு.",
        "sources": [
            "Terramechanics of Rigid Wheels in Deformable Soil (Bekker Theory)",
            "Indian Institute of Management Bangalore Traditional Bullock Cart Survey (Ramaswamy)",
            "Traditional Timber Engineering of South India"
        ],
        "content": "# Large-Diameter Wheel Terramechanics & Dished Spoke Geometry\n\nThe iconic high wheel ($1.5-1.8\\text{ m}$ diameter) of the traditional Tamil *Kattai-Vandi* is an empirical optimization for uninhibited traction across unpaved monsoon clay and dry sandy riverbeds:\n\n**Terramechanical & Structural Principles:**\n- **Sinkage & Obstacle Roll-Over**: In deformable soil (Bekker terramechanics), sinkage $z$ and compaction rolling resistance $R_c$ scale inversely with wheel diameter ($R_c \\propto D^{-(n+1)/(2n+1)}$). A $1.6\\text{-meter}$ wheel bridges deep mud ruts and rolls over $20\\text{ cm}$ boulders with a shallow attack angle, cutting draught bullock effort by $35-45\\%$ compared to small-diameter wheels.\n- **Differential Timber Pairing**: Wheelwrights pair cross-grained *Karuvelam* (*Acacia nilotica* subsp. *indica*) for the hub (*kudam*) and curved rim felloes (*vattai*) to prevent splitting, with straight-grained elastic *Vengai* (*Pterocarpus marsupium*) or teak for the twelve radial spokes (*aarakkaal*)."
    },
    {
        "slug": "concept-thermal-shrink-fit-iron-tyre-hoop-stress-and-radial-pre-compression",
        "category": "concept",
        "file": "concept-thermal-shrink-fit-iron-tyre-hoop-stress-and-radial-pre-compression.md",
        "name_en": "Thermal Shrink-Fit Iron Tyre (Irumbu-Pattai) Hoop Stress & Radial Spoke Pre-Compression",
        "name_ta": "பழுக்கக் காய்ச்சிய இரும்புப் பட்டை வெப்பச் சுருக்க இறுக்கமும் ஆரக்கால் உள்முக அழுத்த இயற்பியலும்",
        "era": "Iron Age to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Thermomechanical physics of the shrink-fitted wrought-iron cart tyre (irumbu-pattai): forging the continuous iron ring 1.2% smaller in circumference than the wooden wheel, expanding it at 650°C (ΔL = αLΔT), and water-quenching it over the felloes so circumferential hoop tension places all twelve spokes and hub joints into permanent radial compression.",
        "summary_ta": "மரச் சக்கரத்தின் சுற்றளவை விடச் சற்றுச் சிறியதாக இரும்புப் பட்டையைப் பற்றவைத்து, நெருப்பில் பழுக்கக் காய்ச்சி விரிவடையச் செய்து, சக்கரத்தில் மாட்டி நீர் ஊற்றிச் சுருங்கச் செய்வதால் ஆணியின்றி இறுகும் வெப்ப இயற்பியல்.",
        "sources": [
            "Thermomechanics of Interference & Shrink-Fit Wheel Assemblies",
            "George Sturt The Wheelwright's Shop & Indian Rural Blacksmith Parallels",
            "Metallurgical History of Wrought-Iron Tyres in South India"
        ],
        "content": "# Thermal Shrink-Fit Iron Tyre Hoop Stress & Pre-Compression\n\nA multi-piece wooden cart wheel made of twelve spokes (*aarakkaal*) and six curved felloe segments (*vattai*) cannot stay rigid under heavy freight solely by wood glue or iron nails; its structural integrity derives from a thermally shrink-fitted wrought-iron hoop (*irumbu-pattai*):\n\n**Thermomechanical Interference Fit:**\n- **Thermal Expansion & Interference ($\\Delta C = \\alpha C \\Delta T$)**: With a linear thermal expansion coefficient $\\alpha \\approx 1.2 \\times 10^{-5}\\text{ K}^{-1}$, heating a $5\\text{-meter}$-circumference wrought-iron ring from $30^\\circ\\text{C}$ to $650^\\circ\\text{C}$ increases its circumference by $\\approx 37\\text{ mm}$ ($\\approx 12\\text{ mm}$ in diameter).\n- **Self-Locking Radial Pre-Stress**: Forged deliberately $25-30\\text{ mm}$ shorter in circumference than the dry wooden wheel, the red-hot tyre slips easily over the rim. Rapid water quenching contracts the steel back toward its cold dimension, generating immense circumferential hoop tension ($\\sigma_\\theta$) that drives radial compressive stress ($p = \\sigma_\\theta t / R$) inward through every felloe joint and spoke tenon into the hub (*kudam*)."
    },
    {
        "slug": "concept-two-wheeled-cart-center-of-gravity-balance-and-nukathadi-yoke-biomechanics",
        "category": "concept",
        "file": "concept-two-wheeled-cart-center-of-gravity-balance-and-nukathadi-yoke-biomechanics.md",
        "name_en": "Two-Wheeled Cart Center-of-Gravity Balancing (Eruthu-Kattu) & Nukathadi Yoke Biomechanics",
        "name_ta": "இருசக்கர வண்டி புவியீர்ப்பு மையச் சமநிலையும் (எருதுக்கட்டு) நுகத்தடி திமில் இழுவை உயிரியக்கவியலும்",
        "era": "Ancient to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Static equilibrium and animal draught biomechanics of the single-axle Tamil bullock cart: trimming cargo forward of the axle (eruthu-kattu) to maintain a slight positive downward force (15–25 kg) on the wooden neck-yoke (nukathadi) ahead of the zebu hump (thimilu), preventing both backward tipping and throat choking on grades.",
        "summary_ta": "வண்டியின் அச்சுக்கு முன்பின் எடையைச் சமன் செய்து நுகத்தடி வழியே காளைகளின் திமில் மீது 15–25 கிலோ அளவிலான மிதமான அழுத்தம் மட்டும் இருக்குமாறு பாரம் ஏற்றும் சமநிலை அறிவியல்.",
        "sources": [
            "Draught Animal Power & Yoke Biomechanics (FAO & ICAR Studies)",
            "Ramaswamy Bullock Cart Modernization & Ergonomics",
            "Traditional Tamil Caravan Loading Practices"
        ],
        "content": "# Two-Wheeled Cart Center-of-Gravity & Nukathadi Biomechanics\n\nBecause a traditional Tamil bullock cart balances its entire $1.0-1.5\\text{ ton}$ payload on a single axle (*achu*), improper cargo trimming immediately injures the draught bullocks:\n\n**Moments & Draught Ergonomics:**\n- **Positive Forward Torque (*Eruthu-Kattu*)**: Teamsters (*vandi-otti*) stack heavy grain sacks directly over the axle bed (*irisu-maram* / *இருசு மரம்*) with the center of mass shifted $8-12\\text{ cm}$ forward of the axle axis. This creates a gentle downward moment that presses the smooth rounded wooden yoke (*nukathadi*) firmly against the front of the zebu bullocks' cervico-thoracic hump (*thimilu*).\n- **Preventing Choking & Rear Tipping**: If loaded tail-heavy (*pin-baaram*), the yoke lifts upward, pulling the braided throat-straps (*poottaan-kayiru* / *பூட்டாங்கயிறு*) tightly against the bullocks' windpipes and choking them; if loaded nose-heavy (*mun-baaram*) on a downhill slope, excessive vertical load crushes the animals' cervical vertebrae."
    },
    {
        "slug": "technology-kudam-hub-turning-twelve-spoke-mortising-and-vattai-felloe-doweling",
        "category": "technology",
        "file": "technology-kudam-hub-turning-twelve-spoke-mortising-and-vattai-felloe-doweling.md",
        "name_en": "Kudam Hub Lathe-Turning, Twelve-Spoke Mortising (Aarakkaal) & Curved Vattai Felloe Joinery",
        "name_ta": "குடம் கடைதல், பன்னிரு ஆரக்கால் துளையிடல் மற்றும் வட்டை இணைக்கும் தச்சுத் தொழில்நுட்பம்",
        "era": "Iron Age to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Wheelwright carpentry (Thatchar craft) of the Tamil wooden cart wheel: seasoning knotted karuvelam blocks in shade, turning the barrel hub (kudam) on a two-man bow/rope lathe, chiseling twelve staggered mortises, driving shouldered vengai spokes (aarakkaal), and joining six curved felloe segments (vattai) with blind hardwood dowels.",
        "summary_ta": "கருவேல மரக் கட்டையைக் கடைந்து குடம் செய்து, பன்னிரண்டு ஆரக்கால்களைப் பொருத்தி, ஆறு வளைந்த வட்டை மரங்களைக் கம்பி ஆணிகளால் இணைத்துச் சக்கரம் உருவாக்கும் தச்சு நுட்பம்.",
        "sources": [
            "Handicrafts & Rural Artisans of Madras Presidency (Thurston & Chatterton)",
            "Viswakarma Thatchar Carpentry Traditions of Tamil Nadu",
            "DakshinaChitra Traditional Transport Collection"
        ],
        "content": "# Kudam Hub Turning, Twelve-Spoke Mortising & Vattai Joinery\n\nConstructing a balanced wooden cart wheel capable of surviving twenty years of rocky village tracks requires precision mortise-and-tenon joinery by the master carpenter (*Thatchar*):\n\n**Wheelwright Assembly Sequence:**\n- **Kudam Turning & Staggered Mortising**: A dense, water-seasoned billet of *karuvelam* (*Acacia nilotica*) is turned on a horizontal two-man rope lathe (*kadai-maram*) into a bulging barrel hub (*kudam*, $35\\text{ cm}$ long, $28\\text{ cm}$ diameter). Twelve rectangular mortises are chiseled around its equator in an alternating staggered pattern (*mun-pin thulai*) to prevent circumferential splitting, and two wrought-iron reinforcement bands (*kuda-pattai*) are shrunk onto the hub ends.\n- **Aarakkaal Spokes & Vattai Felloes**: Twelve tapered *vengai* or teak spokes (*aarakkaal*) are sledged into the hub mortises; their outer round tenons pass into six thick, naturally curved *karuvelam* felloe arcs (*vattai*) pinned end-to-end with internal iron or hardwood dowels (*kambi*)."
    },
    {
        "slug": "technology-pattai-kuzhi-circular-fire-trench-tyre-heating-and-rapid-water-quenching",
        "category": "technology",
        "file": "technology-pattai-kuzhi-circular-fire-trench-tyre-heating-and-rapid-water-quenching.md",
        "name_en": "Pattai-Kuzhi Circular Trench Firing, Alavu-Chakkaram Traveller Gauging & Tyre Shrink-Quenching",
        "name_ta": "பட்டைக்குழி வட்ட உலை சூடேற்றல், அளவுச் சக்கர அளவீடு மற்றும் இரும்புப் பட்டை நீர் ஊற்றி இறுக்கும் நுட்பம்",
        "era": "Iron Age to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Blacksmith pyrotechnic process (Kollan craft) for shoeing wooden cart wheels: rolling a chalked iron traveller disc (alavu-chakkaram) around the rim and inside the forged tyre to set interference allowance, heating the hoop in a circular cow-dung trench furnace (pattai-kuzhi), levering it onto the wheel in a hub pit, and quenching with water.",
        "summary_ta": "அளவுச் சக்கரம் கொண்டு மரச் சக்கரத்தின் சுற்றளவை அளந்து, வரட்டி அடுக்கிய வட்டப் பட்டைக்குழியில் இரும்புப் பட்டையைப் பழுக்கக் காய்ச்சி, சக்கரத்தில் மாட்டி உடனடியாக நீர் ஊற்றி இறுக்கும் கொல்லர் தொழில்நுட்பம்.",
        "sources": [
            "Ethnography of Village Blacksmiths (Kollan) in Southern Tamil Nadu",
            "Traditional Iron-Working & Wheelwrighting in Virudhunagar and Madurai",
            "History of Indian Technology: Rural Transport Craft"
        ],
        "content": "# Pattai-Kuzhi Trench Firing & Iron Tyre Shrink-Quenching\n\nShoeing a wooden wheel with its $12\\text{ mm}$-thick wrought-iron or mild-steel tyre (*pattai-poduthal*) is a dramatic, time-critical collaboration between the village blacksmith (*Kollan*) and carpenter (*Thatchar*):\n\n**Pyrotechnic Procedure:**\n- **Alavu-Chakkaram Circumference Gauging**: A small hand-held iron measuring wheel (*alavu-chakkaram* or *traveller*) with a chalk mark is rolled once around the outer wooden rim (*vattai*) and then rolled along the flat iron bar before scarf-welding the ends in the forge, subtracting a precise interference allowance ($25-30\\text{ mm}$) so the cold hoop is smaller than the wheel.\n- **Pattai-Kuzhi Firing & Quenching**: The welded hoop is buried inside a shallow circular ring-trench (*pattai-kuzhi*) fueled with dried cow-dung cakes (*varatti*) and paddy husk until it glows uniform cherry-red ($650^\\circ\\text{C}$). Three smiths hoist the glowing ring with hooked tongs (*kuradu*), drop it over the horizontal wooden wheel resting on a central hub-pit, hammer it flush through clouds of white wood-smoke, and douse it rapidly with buckets of water before the felloes char deeply."
    },
    {
        "slug": "artifact-achu-axle-achaani-linchpin-kandennai-grease-pot-and-mutti-katta-brake-props",
        "category": "artifact",
        "file": "artifact-achu-axle-achaani-linchpin-kandennai-grease-pot-and-mutti-katta-brake-props.md",
        "name_en": "Achu Iron Axles, Achaani Linchpins, Kandennai Tar-Grease Pots & Thaangi-Kattai Drop-Props",
        "name_ta": "இரும்பு அச்சு, அச்சாணி, கண்டெண்ணெய்க் கிண்ணம் (மைக் கிண்ணம்) மற்றும் தாங்கிக்கட்டை உபகரணங்கள்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Essential mechanical hardware slung beneath the traditional Tamil freight cart: the forged square-beam iron axle (achu) with cylindrical journal spindles, S-curved iron linchpins (achaani) and dust caps, the swinging coconut-shell castor-tar grease pot (kandennai-kinnam), and hinged front/rear wooden rest-props (thaangi-kattai).",
        "summary_ta": "மாட்டு வண்டியின் அடிப்பாகத்தில் பொருத்தப்படும் சதுர இரும்பு அச்சு, சக்கரம் கழலாமல் தடுக்கும் அச்சாணி, அச்சுக்குப் பூசத் தொங்கவிடப்படும் கண்டெண்ணெய்க் கிண்ணம் மற்றும் வண்டி சாயாமல் நிறுத்தும் தாங்கிக்கட்டை.",
        "sources": [
            "Madras Government Museum Traditional Transport Artifacts",
            "Perumpanarruppadai & Tirukkural Commentaries on Achu and Achaani",
            "Rural Agricultural Engineering Implements of Tamil Nadu"
        ],
        "content": "# Achu Axles, Achaani Linchpins & Kandennai Grease Pots\n\nBeneath the bamboo and timber deck (*vandi-koodu*) of every long-distance Tamil freight cart hangs a standardized suite of tribological and safety hardware:\n\n**Undercarriage Components:**\n- **Achu (Axle) & Achaani (Linchpin)**: A solid square-sectioned forged wrought-iron bar ($50\\text{ mm}$ square) bolted into a heavy hardwood axle-bed (*irisu-kattai*), terminating in turned cylindrical journals that ride inside cast-iron hub bushes (*kuzhai*). Each wheel is retained on the journal by a washer collar and a curved iron linchpin (*achaani*) slotted through a transverse eye near the spindle tip.\n- **Kandennai-Kinnam (Lubrication Pot) & Thaangi-Kattai**: Slung by a coir cord beneath the axle is a hollowed coconut shell or palmyra-wood cup (*kandennai-kinnam* or *mai-kinnam*) filled with thick black axle grease compounded from oxidized castor oil (*aamannakku-ennai*), pine tar, and charcoal soot. Hinged wooden drop-props (*thaangi-kattai* at the front pole and *mutti-kattai* at the rear) swing down to level the cart when bullocks are unyoked."
    },
    {
        "slug": "artifact-koondu-vandi-arched-bamboo-canopy-carts-and-kongu-rekla-racing-chariots",
        "category": "artifact",
        "file": "artifact-koondu-vandi-arched-bamboo-canopy-carts-and-kongu-rekla-racing-chariots.md",
        "name_en": "Koondu-Vandi Arched Bamboo-Hood Passenger Carts & Lightweight Rekla Racing Chariots",
        "name_ta": "கூண்டு வண்டி (வில் வண்டி) மூங்கில் கொட்டகைப் பயண வண்டிகளும் கொங்கு ரெக்ளாப் பந்தய வண்டிகளும்",
        "era": "Medieval to Modern Era",
        "year_start": 1200,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Specialized passenger and high-speed bullock vehicles of Tamil Nadu: the vaulted split-bamboo and braided coconut-frond canopy cart (koondu-vandi / vil-vandi) providing shaded family transport for weddings and temple pilgrimages, and the skeletonized two-wheeled Rekla racing chariot pulled by trotting Kangayam bulls.",
        "summary_ta": "குடும்பப் பயணம், திருமணம் மற்றும் குலதெய்வக் கோவில் யாத்திரைகளுக்குப் பயன்பட்ட வளைந்த மூங்கில் கூண்டு வண்டிகளும் (வில் வண்டி), காங்கேயம் காளைகள் பூட்டப்படும் இலகுரக ரெக்ளாப் பந்தய வண்டிகளும்.",
        "sources": [
            "Folklore & Transport Heritage of Kongu Nadu and Pandya Nadu",
            "Coimbatore & Madura District Gazetteers",
            "DakshinaChitra Heritage Cart Pavilion"
        ],
        "content": "# Koondu-Vandi Arched Canopy Carts & Rekla Racing Chariots\n\nAlongside open flatbed agricultural carts (*mottai-vandi* / *paara-vandi*), Tamil wheelwrights built specialized covered coaches and high-speed racing gigs:\n\n**Vehicle Typologies:**\n- **Koondu-Vandi / Vil-Vandi (Arched Canopy Coach)**: Over a sprung or cushioned wooden deck, split *kal-moongil* bamboo hoops are bent into a semi-cylindrical barrel vault and thatched with double layers of woven coconut-frond mats (*keetru*) and palmyra rain-shields (*thatti*). Spread inside with paddy straw and quilted cotton mattresses, and hung with brass jingle bells (*salangai*) on the bullocks' horns, the *koondu-vandi* served for centuries as the classic nocturnal family coach for rural weddings and *Kula-Deivam* pilgrimages.\n- **Rekla-Vandi (Racing Chariot)**: Popular across the Kongu and southern Pandya plains, the *Rekla* features a minimalist triangular iron-and-teak frame, a single driver's perch over the axle, and tall, ultra-thin multi-spoked wheels designed for $35\\text{ km/h}$ trotting sprints."
    },
    {
        "slug": "institution-kammalar-thatchar-kollan-wheelwright-guilds-and-pettai-caravan-staging-depots",
        "category": "institution",
        "file": "institution-kammalar-thatchar-kollan-wheelwright-guilds-and-pettai-caravan-staging-depots.md",
        "name_en": "Thatchar-Kollan Joint Wheelwright Pattarai Guilds, Vandi-Pettai Caravan Depots & Sumaithangi",
        "name_ta": "தச்சர்-கொல்லர் கூட்டு வண்டிப் பட்டறைகள், வண்டிப் பேட்டை வணிகத் தங்குமிடங்கள் மற்றும் சுமைதாங்கி",
        "era": "Sangam to Colonial Era",
        "year_start": -200,
        "year_end": 1950,
        "thinai": "mullai",
        "summary_en": "Institutional infrastructure of Tamil overland cart trade: joint wheelwright workshops (vandi-pattarai) uniting Kammalar carpenters (Thatchar) and blacksmiths (Kollan), fortified merchant caravan yards (Vandi-Pettai) with stone watering troughs and fodder brokerages, and wayside stone load-rests (sumaithangi) along royal highways (Peru-Vazhi).",
        "summary_ta": "மரத் தச்சரும் இரும்புக் கொல்லரும் இணைந்து செயல்பட்ட வண்டிப் பட்டறைகள், நூற்றுக்கணக்கான பார வண்டிகள் தங்கி வாணிகம் செய்த வண்டிப் பேட்டைகள் மற்றும் பெருவழிச் சாலைகளின் கற்கள் (சுமைதாங்கி, தண்ணீர்த் தொட்டி).",
        "sources": [
            "South Indian Inscriptions (Peru-Vazhi & Pettai Trade Charters)",
            "Champakalakshmi Trade, Ideology and Urbanization in South India",
            "Madura & Tinnevelly District Manuals"
        ],
        "content": "# Thatchar-Kollan Wheelwright Pattarais & Vandi-Pettai Caravan Depots\n\nLong-distance bullock-cart freight (*saathu*) along the ancient *Peru-Vazhi* trunk roads depended on a coordinated network of artisanal workshops and wayside staging depots:\n\n**Artisanal & Mercantile Institutions:**\n- **Joint Thatchar-Kollan Vandi-Pattarai**: Within the fivefold *Kammalar* (*Viswakarma*) artisan guild, every major market town maintained dedicated wheelwright yards (*vandi-pattarai*) where the wood-carpenter (*Thatchar*) and iron-smith (*Kollan*) worked side-by-side under shared custom or cash contracts to build new carts, re-bush worn hubs, and re-shrink loose iron tyres.\n- **Vandi-Pettai Staging Enclosures**: At intervals of one night's bullock march ($25-30\\text{ km}$), merchant guilds (*Nagarathar*, *Nadar* *Uravinmurai*, and *Chettiar* syndicates) maintained walled *Vandi-Pettai* compounds equipped with monolithic granite water troughs (*kal-thotti*), fodder stacks (*cholam-thattu*), armed night watchmen, and commodity weighing beams (*thulaa-kkol*)."
    },
    {
        "slug": "place-virudhunagar-ancient-pandya-peru-vazhi-bullock-cart-and-wheelwright-haven",
        "category": "place",
        "file": "place-virudhunagar-ancient-pandya-peru-vazhi-bullock-cart-and-wheelwright-haven.md",
        "name_en": "Virudhunagar (Virudupatti): Ancient Pandya Peru-Vazhi Bullock-Cart Pettai & Wheelwright Haven",
        "name_ta": "விருதுநகர் (விருதுப்பட்டி) - பாண்டிய நாட்டுப் பெருவழி மாட்டு வண்டிப் பேட்டை மற்றும் சக்கரப் பட்டறைத் தளம்",
        "era": "Medieval Pandya to Modern Era",
        "year_start": 1100,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Historic inland mercantile hub of Virudhunagar (formerly Virudupatti, lat 9.5850, lng 77.9570, thinai: mullai) on the ancient Pandya North-South Peru-Vazhi trade highway between Madurai and Tuticorin, celebrated for its vast Vandi-Pettai bullock-cart freight depots and heavy-duty karuvelam wheelwright workshops.",
        "summary_ta": "மதுரைக்கும் தூத்துக்குடித் துறைமுகத்திற்கும் இடைப்பட்ட பாண்டியப் பெருவழியில் அமைந்த விருதுநகர் (அட்சரேகை 9.5850, தீர்க்கரேகை 77.9570): புகழ்பெற்ற மாட்டு வண்டிப் பேட்டைகள் மற்றும் கருவேல மரச் சக்கரப் பட்டறைகளின் மையம்.",
        "sources": [
            "Ramnad & Tinnevelly District Gazetteers (Pate 1917)",
            "Hardgrave The Nadars of Tamilnad: Pettais and Cart Caravans of Virudupatti",
            "Economic History of Southern Pandya Overland Trade"
        ],
        "content": "# Virudhunagar: Pandya Peru-Vazhi Bullock-Cart & Wheelwright Haven\n\nSituated at latitude $9.5850^\\circ\\text{ N}$, longitude $77.9570^\\circ\\text{ E}$ in the dry *mullai-karisal* (black-cotton soil) plains south of Madurai along the Kaushika river, Virudhunagar (historically *Virudupatti*) rose to prominence as the supreme bullock-cart logistics and wheelwright capital of southern Tamil Nadu:\n\n**Strategic & Craft Prominence:**\n- **Nexus of the Southern Peru-Vazhi**: Positioned halfway along the ancient Pandya overland trunk road connecting Madurai with the Gulf of Mannar ports (Kayalpattinam, Kulasekharapatnam, and Tuticorin) and the Western Ghats passes (Shencottah and Srivilliputhur), Virudhunagar's fortified *Pettai* yards received over a thousand two-bullock freight carts daily loaded with raw cotton, dried chillies, coriander, jaggery, and gingelly oil.\n- **Karuvelam Wheelwright Cluster**: Surrounded by dense *karisal* plains rich in rock-hard *Acacia nilotica* (*karuvelam*) timber, Virudhunagar's *vandi-pattarai* workshops perfected oversized, iron-shod *paara-vandi* wheels engineered to haul two-ton loads through sticky black-cotton mud without bogging down."
    }
]

EDGES = [
    [
        "text-tirukkural-and-sangam-accounts-of-saagadam-achaani-and-umanar-salt-carts",
        "documents",
        "artifact-achu-axle-achaani-linchpin-kandennai-grease-pot-and-mutti-katta-brake-props",
        "material_culture",
        "Sangam to Post-Sangam Era",
        "Tirukkural couplets 475 and 667 and Perumpanarruppadai document cart axles (achu), linchpins (achaani), and spare axles on Umanar caravans.",
        "Tirukkural & Perumpanarruppadai"
    ],
    [
        "concept-large-diameter-spoked-wheel-rolling-resistance-and-dished-spoke-mechanics",
        "governs",
        "technology-kudam-hub-turning-twelve-spoke-mortising-and-vattai-felloe-doweling",
        "material_culture",
        "Iron Age to Modern Era",
        "Terramechanical rolling-resistance reduction and dished-spoke lateral stiffness govern the 1.6-meter wheel geometry and karuvelam-vengai timber pairing.",
        "Bekker Terramechanics & IIMB Survey"
    ],
    [
        "concept-thermal-shrink-fit-iron-tyre-hoop-stress-and-radial-pre-compression",
        "governs",
        "technology-pattai-kuzhi-circular-fire-trench-tyre-heating-and-rapid-water-quenching",
        "material_culture",
        "Iron Age to Modern Era",
        "Linear thermal expansion (ΔL = αLΔT) and hoop-stress pre-compression govern the interference sizing and quenching of the wrought-iron tyre.",
        "Shrink-Fit Thermomechanics"
    ],
    [
        "concept-two-wheeled-cart-center-of-gravity-balance-and-nukathadi-yoke-biomechanics",
        "guides",
        "artifact-achu-axle-achaani-linchpin-kandennai-grease-pot-and-mutti-katta-brake-props",
        "material_culture",
        "Ancient to Modern Era",
        "Single-axle center-of-gravity balancing (eruthu-kattu) guides axle placement, yoke mounting, and front/rear thaangi-kattai drop-props.",
        "ICAR Draught Animal Ergonomics"
    ],
    [
        "technology-kudam-hub-turning-twelve-spoke-mortising-and-vattai-felloe-doweling",
        "prepares",
        "technology-pattai-kuzhi-circular-fire-trench-tyre-heating-and-rapid-water-quenching",
        "material_culture",
        "Iron Age to Modern Era",
        "Lathe-turned karuvelam hubs, twelve mortised spokes, and doweled vattai felloes assemble the wooden wheel ready for hot iron tyre shoeing.",
        "Madras Presidency Artisans Survey"
    ],
    [
        "technology-kudam-hub-turning-twelve-spoke-mortising-and-vattai-felloe-doweling",
        "fabricates",
        "artifact-koondu-vandi-arched-bamboo-canopy-carts-and-kongu-rekla-racing-chariots",
        "material_culture",
        "Medieval to Modern Era",
        "Precision wheelwright joinery and bent bamboo frame construction fabricate arched koondu-vandi passenger coaches and lightweight Rekla racing gigs.",
        "DakshinaChitra Transport Catalog"
    ],
    [
        "institution-kammalar-thatchar-kollan-wheelwright-guilds-and-pettai-caravan-staging-depots",
        "executes",
        "technology-pattai-kuzhi-circular-fire-trench-tyre-heating-and-rapid-water-quenching",
        "material_culture",
        "Sangam to Colonial Era",
        "Joint workshops of Kammalar Thatchar carpenters and Kollan blacksmiths execute pattai-kuzhi trench firing and shrink-fitting of cart tyres.",
        "Viswakarma Guild Ethnography"
    ],
    [
        "institution-kammalar-thatchar-kollan-wheelwright-guilds-and-pettai-caravan-staging-depots",
        "maintains",
        "concept-two-wheeled-cart-center-of-gravity-balance-and-nukathadi-yoke-biomechanics",
        "material_culture",
        "Sangam to Colonial Era",
        "Fortified Vandi-Pettai caravan depots maintain weighing beams, loading platforms, and axle-greasing stations for balanced overland freight.",
        "Hardgrave Nadars of Tamilnad"
    ],
    [
        "place-virudhunagar-ancient-pandya-peru-vazhi-bullock-cart-and-wheelwright-haven",
        "hosts",
        "institution-kammalar-thatchar-kollan-wheelwright-guilds-and-pettai-caravan-staging-depots",
        "material_culture",
        "Medieval Pandya to Modern Era",
        "Virudhunagar on the southern Pandya Peru-Vazhi hosts major Vandi-Pettai freight enclosures and heavy-duty karuvelam wheelwright pattarais.",
        "Tinnevelly & Ramnad Gazetteers"
    ],
    [
        "text-tirukkural-and-sangam-accounts-of-saagadam-achaani-and-umanar-salt-carts",
        "contextualizes",
        "place-virudhunagar-ancient-pandya-peru-vazhi-bullock-cart-and-wheelwright-haven",
        "material_culture",
        "Sangam to Post-Sangam Era",
        "Classical accounts of Umanar and inland merchant cart convoys contextualize the southern Pandya Peru-Vazhi corridor centered at Virudhunagar.",
        "Ahananuru & Pandya Trade History"
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
