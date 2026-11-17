#!/usr/bin/env python3
"""
Harvester: Batch 45 - Ancient Tamil Riverine Coracles, Split-Bamboo Basket-Boats, Ford Crossings & Gorge Navigation
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
        "slug": "text-sangam-and-historical-accounts-of-ambhi-punai-and-kaveri-coracles",
        "category": "text",
        "file": "text-sangam-and-historical-accounts-of-ambhi-punai-and-kaveri-coracles.md",
        "name_en": "Sangam & Historical Accounts of Ambhi, Punai Rafts and Hide-Clad Kaveri Coracles",
        "name_ta": "சங்க இலக்கிய அம்பி, புணை மற்றும் காவேரி பரிசல் துறை பற்றிய வரலாற்றுக் குறிப்புகள்",
        "era": "Sangam to Colonial Era",
        "year_start": -300,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Literary and historical documentation of inland Tamil river craft: Sangam poems (Kuruntokai, Ahananuru, Paripadal) describing bamboo floats (punai) and ferry boats (ambhi / thoni) crossing the Kaveri and Vaigai in spate, alongside medieval inscriptional and traveler accounts of hide-covered circular coracles (parisal).",
        "summary_ta": "குறுந்தொகை, அகநானூறு, பரிபாடல் உள்ளிட்ட இலக்கியங்களில் குறிப்பிடப்படும் அம்பி, புணை, தோணி மற்றும் காவேரி ஆற்றின் சுழல்களைக் கடக்கும் வட்ட வடிவ தோல் பரிசல்கள் பற்றிய வரலாற்றுச் சான்றுகள்.",
        "sources": [
            "Kuruntokai",
            "Ahananuru",
            "Paripadal",
            "Buchanan & Colonial Madras District Gazetteers (Coimbatore / Salem)"
        ],
        "content": "# Sangam & Historical Accounts of River Ferries and Coracles\n\nInland river crossings across the seasonal floods of the Kaveri, Bhavani, Amaravathi, and Vaigai generated a distinct corpus of Tamil literary and historical descriptions:\n\n**Documentary Evidence:**\n- **Sangam River Craft (*Punai, Ambhi & Thoni*)**: Poems in *Ahananuru*, *Kuruntokai*, and *Paripadal* depict swollen monsoon rivers (*pudhu-punal*) where swimmers cling to buoyant bamboo rafts (*punai*) and ferrymen pole low-draft river boats (*ambhi* and *thoni*) from stone landing fords (*thurai*).\n- **Hide-Sheathed Circular Coracles (*Parisal*)**: Medieval Kannada-Tamil epigraphs along the upper and middle Kaveri and 18th–19th century accounts (such as Francis Buchanan's journey through Coimbatore and Salem) describe circular woven-bamboo basket boats covered in taut buffalo hide, ferrying passengers, grain sacks, and troops across rocky rapids."
    },
    {
        "slug": "concept-parisal-paraboloid-buoyancy-shallow-draft-and-eddy-stability",
        "category": "concept",
        "file": "concept-parisal-paraboloid-buoyancy-shallow-draft-and-eddy-stability.md",
        "name_en": "Parisal Paraboloid Shell Buoyancy, Ultra-Shallow Draft & Whirlpool Eddy Stability",
        "name_ta": "பரிசல் கிண்ண வடிவ மிதப்பு விசை, குறைந்த ஆழ மிதப்பு மற்றும் நீர்ச்சுழல் சமநிலை இயற்பியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Hydrostatic and hydrodynamic physics of the circular Tamil coracle (Parisal): wide paraboloid floor distributing payload over 4-5 square meters for a draft under 15 cm, keel-less omnidirectional hull shedding rock impacts and rotational river whirlpools without capsizing.",
        "summary_ta": "வட்ட வடிவ பரிசலின் நீரியக்கவியல்: அகன்ற அடிப்பாகத்தால் 15 செ.மீ ஆழ நீரிலும் 500 கிலோ எடையைத் தாங்கி மிதக்கும் திறன், அடிப்பாகக் கட்டையின்மையால் பாறை இடிப்பு மற்றும் நீர்ச்சுழலில் கவிழாத சமநிலை.",
        "sources": [
            "Hydrodynamics of Traditional Indian Inland Watercraft",
            "Hornell Water Transport: Origins & Early Evolution",
            "Salem & Dharmapuri District Gazetteers"
        ],
        "content": "# Parisal Paraboloid Buoyancy & Whirlpool Stability\n\nThe circular *Parisal* coracle ($2.2-2.8\\text{ m}$ rim diameter, $\\sim 0.6\\text{ m}$ depth) is hydrodynamically optimized for boulder-choked gorges where keeled wooden boats would splinter:\n\n**Hydrostatic & Fluid Mechanics:**\n- **Ultra-Shallow Displacement Draft**: Because displaced water volume scales with $\\pi r^2 h$, a $2.5\\text{ m}$ diameter *parisal* carrying $400\\text{ kg}$ of passengers or cargo draws less than $10-12\\text{ cm}$ of water, gliding safely over submerged granite ledges.\n- **Keel-Less Vortex Shedding**: A conventional keeled boat caught sideways in a river whirlpool experiences lateral torque against its keel that rolls the hull over. The radially symmetric, smooth-bottomed *parisal* offers no lateral keel surface to the current; instead, it rotates harmlessly on its vertical axis while riding up the eddy boundary.\n- **Elastic Impact Absorption**: The interlaced bamboo dome flexes inward when grazing submerged boulders, rebounding without structural fracture."
    },
    {
        "slug": "technology-split-bamboo-hexagonal-lattice-weaving-and-hide-pitch-waterproofing",
        "category": "technology",
        "file": "technology-split-bamboo-hexagonal-lattice-weaving-and-hide-pitch-waterproofing.md",
        "name_en": "Split-Bamboo Radial Lattice Weaving, Gunwale Ring Lashing & Hide-Pitch Waterproofing",
        "name_ta": "மூங்கில் பிளாச்சு பின்னல், விளிம்பு வளையக் கட்டு மற்றும் எருமைத்தோல்-கீல் நீர்ப்புகாப் பூச்சு",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Craft sequence of building a Kaveri Parisal: splitting seasoned Dendrocalamus strictus hill bamboo into flexible laths, staking an inverted dome over an earthen mound mold, binding the thick gunwale hoop, and sheathing the exterior in stitched buffalo hide (historically) or bitumen-coated canvas.",
        "summary_ta": "பரிசல் கட்டும் தொழில்நுட்பம்: கல் மூங்கிலைப் பிளந்து மண் மேட்டு அச்சின் மேல் குறுக்கு-நெடுக்காகப் பின்னி, விளிம்பு வளையம் கட்டி, வெளிப்புறத்தில் பதப்படுத்திய எருமைத் தோல் அல்லது தார் பூசிய உறை போர்த்தும் முறை.",
        "sources": [
            "James Hornell Indian Coracles and Basket Boats",
            "Ethnography of Hogenakkal Coracle Builders",
            "Indian Journal of History of Science"
        ],
        "content": "# Split-Bamboo Lattice Weaving & Waterproof Sheathing\n\nConstructing a *Parisal* combines basketry tension-shell engineering with waterproof membrane craft:\n\n**Construction Sequence:**\n1. **Bamboo Lath Splitting**: Mature culms of solid hill bamboo (*kal-moongil*, *Dendrocalamus strictus*) are split longitudinally into uniform strips ($2.5\\text{ cm}$ wide, $4-5\\text{ mm}$ thick) and soaked in river water for pliability.\n2. **Mound-Mold Interlacing**: About 24 to 32 long laths are laid in a radial star grid over a hemispherical earthen mound and interlaced with concentric bamboo hoops to form a rigid, geodesic-like open basket. A thick bundle of split bamboo is lashed around the rim to form the gunwale ring.\n3. **Waterproof Skinning**: Historically, two or three cured ox or water-buffalo hides were soaked, stretched taut over the convex exterior, and sewn to the gunwale with leather thongs, sealed with vegetable oil and tree resin (in the late 20th century, tarred canvas/HDPE sheets and boiling bitumen replaced hide while preserving the identical bamboo frame)."
    },
    {
        "slug": "technology-single-paddle-sculling-figure-eight-draw-stroke-and-gorge-ferrying",
        "category": "technology",
        "file": "technology-single-paddle-sculling-figure-eight-draw-stroke-and-gorge-ferrying.md",
        "name_en": "Single-Paddle Bow Sculling (mun-thuzhaavu), Figure-Eight Hydrofoil Traction & Ferry Angling",
        "name_ta": "ஒற்றைத் துடுப்பு எட்டு-வடிவ முன் துழாவல், சுழற்சி கட்டுப்பாடு மற்றும் ஆற்றுக் குறுக்குக் கடப்பு",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Propulsion kinematics of a circular keel-less coracle: standing or kneeling at the forward rim and sweeping a single short paddle in a continuous submerged figure-eight sculling stroke over the bow to pull the boat straight forward without spinning, and ferry-angling across fast currents.",
        "summary_ta": "சுக்கானில்லாத வட்டப் பரிசலை நேர்க்கோட்டில் செலுத்தும் ஒற்றைத் துடுப்பு நுட்பம்: பரிசலின் முன்பக்கம் நின்று நீருக்குள் எட்டு (8) வடிவில் துடுப்பை அசைத்துச் சுழலாமல் முன்னோக்கி இழுக்கும் முறை.",
        "sources": [
            "James Hornell Indian Coracles and Basket Boats",
            "Fluid Mechanics of Sculling Propulsion",
            "Kaveri River Navigation Ethnography"
        ],
        "content": "# Single-Paddle Bow Sculling & Gorge Ferrying\n\nBecause a circular coracle has neither bow nor stern nor rudder, a conventional side-stroke simply spins the craft in place. Tamil *Odaikkarar* boatmen master two distinct propulsion modes:\n\n**Propulsion Kinematics:**\n1. **Figure-Eight Bow Sculling (*Mun-Thuzhaavu*)**: Standing or crouching at the leading edge, the boatman plunges a single short, broad-bladed wooden paddle (*thuduppu*) vertically into the water ahead of the rim and sweeps it laterally left and right in a continuous figure-eight ($\\infty$) path while angling the blade pitch on each stroke. This generates forward hydrofoil lift while canceling rotational torque, pulling the *parisal* straight ahead.\n2. **Cross-Current Ferry Angling**: When crossing a swift river between two stone *thoni-thurai* steps, the boatman aims the coracle $30^\\circ-45^\\circ$ upstream into the current, using eddy back-currents along the far bank to glide into the landing slip."
    },
    {
        "slug": "artifact-parisal-bamboo-hull-wooden-sculling-paddles-and-coracle-cast-nets",
        "category": "artifact",
        "file": "artifact-parisal-bamboo-hull-wooden-sculling-paddles-and-coracle-cast-nets.md",
        "name_en": "Woven Bamboo Parisal Shells, Broad-Bladed Thuduppu Paddles & Gorge Cast-Nets",
        "name_ta": "மூங்கில் பரிசல் கூடுகள், அகன்ற மரத் துடுப்புகள் மற்றும் ஆற்று வீச்சு வலைகள்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Material toolkit of the Kaveri coracle boatman and inland river fisher: inverted-dome bamboo coracles, one-piece hardwood paddles (thuduppu), hide-stitching awls and pitch cauldrons, weighted circular cast-nets (veechu-valai), and wicker fish creels (parisal-koodai).",
        "summary_ta": "காவேரி பரிசல் ஓட்டிகள் மற்றும் ஆற்று மீனவர்களின் கருவிகள்: மூங்கில் பரிசல் கூடு, ஒற்றை மரத் துடுப்பு, தோல் தைக்கும் ஊசி, ஈய குண்டு கட்டிய வீச்சு வலை மற்றும் மீன் கூடைகள்.",
        "sources": [
            "Madras Museum Ethnographic Watercraft Collection",
            "Inland Fisheries of the Cauvery River Reports",
            "Hornell Indian Coracles"
        ],
        "content": "# Parisal Hulls, Sculling Paddles & Gorge Cast-Nets\n\nThe lightweight equipment of the Kaveri coracle boatman is designed so a single person can carry the entire boat and fishing kit on their head over rocky portages:\n\n**Artifact Inventory:**\n- **The Portable Coracle Shell**: Weighing $18-25\\text{ kg}$ when dry, the *parisal* is inverted over the boatman's shoulders like a giant umbrella hat to walk back upstream along canyon trails after a downstream run, or inverted on the riverbank as a rain shelter.\n- **Thuduppu Sculling Paddle**: Carved from a single piece of seasoned *vaagai* or teak wood ($1.1-1.3\\text{ m}$ long) with a T-grip handle and a thin, slightly spooned oval blade optimized for low-wrist-fatigue figure-eight sculling.\n- **Coracle Fishing Gear**: Because the *parisal* has no projecting cleats that snag mesh, inland fishers cast circular weighted *veechu-valai* nets and haul gill-nets directly over the smooth rounded gunwale."
    },
    {
        "slug": "concept-thoni-thurai-stone-ford-hydraulics-and-seasonal-flood-ferry-routes",
        "category": "concept",
        "file": "concept-thoni-thurai-stone-ford-hydraulics-and-seasonal-flood-ferry-routes.md",
        "name_en": "Thoni-Thurai Stone Ferry-Ghat Hydraulics, Slack-Water Eddy Siting & Flood Stage Gauging",
        "name_ta": "தோணித்துறை கற்படித்துறை நீரியல், சுழல் ஒதுக்கத் தேர்வு மற்றும் வெள்ளப் பெருக்கு அளவீடு",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Hydraulic siting and architectural layout of traditional Tamil river ferry crossings (thoni-thurai / parisal-thurai): pairing upstream launch steps with downstream slack-water eddies to compensate for lateral current drift, stepped granite ghats accommodating 5-meter monsoon stage variations, and guide-rope crossings.",
        "summary_ta": "ஆற்றுத் தோணித்துறை மற்றும் பரிசல் துறைகளின் நீரியல் அமைப்பு: நீரோட்ட இழுப்பைக் கணக்கிட்டு எதிர்க்கரை சாய்வுப் புள்ளியில் அமைக்கப்படும் கற்படித்துறைகள் மற்றும் வெள்ள மட்டப் படிகள்.",
        "sources": [
            "Inscriptions of the Kaveri & Bhavani River Crossings",
            "Coimbatore & Trichinopoly District Gazetteers",
            "Traditional River Engineering in South India"
        ],
        "content": "# Thoni-Thurai Stone Ferry-Ghat Hydraulics\n\nRiver ferry crossings (*Thoni-Thurai* or *Parisal-Thurai*) along the Kaveri, Bhavani, Noyyal, and Vaigai were sited using empirical river-mechanics principles:\n\n**Hydraulic Siting Principles:**\n- **Diagonal Drift Offset**: Ferrymen never placed opposing landing ghats directly opposite one another in fast water; instead, twin landing steps were paired with natural rocky promontories that created quiet slack-water counter-eddies (*odukkam*) on both banks, allowing coracles to launch in still water, ride the main chute diagonally, and duck into the opposite eddy.\n- **Stepped Granite Ghats (*Padithurai*)**: Long flights of dressed granite steps descended from the high flood bank down to the summer low-water channel, providing a firm, mud-free footing for passengers and pack bullocks at every river stage between the Southwest (*Aadi-Perukku*) and Northeast monsoons."
    },
    {
        "slug": "institution-odaikkarar-ferrymen-guilds-and-royal-thurai-toll-charters",
        "category": "institution",
        "file": "institution-odaikkarar-ferrymen-guilds-and-royal-thurai-toll-charters.md",
        "name_en": "Odaikkarar Ferrymen Guilds, Thurai-Kaani Rights & Chathiram River-Crossing Endowments",
        "name_ta": "ஓடைக்காரர் பரிசல் ஓட்டிகள் முறைமை, துறைக்காணி உரிமை மற்றும் ஆற்றுத்துறைச் சத்திர அறக்கட்டளைகள்",
        "era": "Medieval to Colonial Era",
        "year_start": 900,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Institutional governance of inland Tamil river crossings: hereditary ferryman families (Odaikkarar / Ambhikkarar / Sembadavar) holding village service grants (thurai-manyam) to ferry villagers free against annual grain shares (swatantram), alongside royal toll auctions and charitable wayside rest-houses (chathiram).",
        "summary_ta": "ஆற்றுப் போக்குவரத்தை நிர்வகித்த ஓடைக்காரர் மற்றும் அம்பிக்காரர் சமூக அமைப்பு: கிராம மக்களைக் கரையேற்ற வழங்கப்பட்ட துறை மானியம், தானியப் பங்கு மற்றும் ஆற்றுத்துறைச் சத்திர தர்மங்கள்.",
        "sources": [
            "South Indian Inscriptions (Kaveri Ferry Endowments)",
            "Salem & Coimbatore District Manuals",
            "Dharma-Chathiram Records of Thanjavur"
        ],
        "content": "# Odaikkarar Ferrymen Guilds & Thurai-Kaani Charters\n\nBefore modern masonry bridges spanned the wide rivers of Tamil Nadu, inland trade and pilgrimage depended on regulated ferry corporations:\n\n**Institutional Arrangements:**\n- **Hereditary Service Tenure (*Thurai-Manyam*)**: Village assemblies granted hereditary ferrymen (*Odaikkarar*) wet-land plots or fixed harvest shares (*mera* / *kalam* of paddy per threshing floor) in exchange for maintaining seaworthy coracles and ferrying local residents, livestock, and agricultural implements free of charge year-round.\n- **Commercial Caravan Tolls (*Thurai-Sungam*)**: Long-distance merchant caravans (*saathu*) transporting salt, jaggery, cotton, and betel paid regulated per-pack-load ferry fees, a portion of which was endowed to local riverside temples.\n- **Free Ferry Charities (*Thoni-Dharmam*)**: Royal and merchant philanthropists established *chathiram* rest-houses at major crossings with endowments paying boatmen to ferry pilgrims without fee during festival floods."
    },
    {
        "slug": "place-hogenakkal-ancient-kaveri-gorge-parisal-coracle-haven",
        "category": "place",
        "file": "place-hogenakkal-ancient-kaveri-gorge-parisal-coracle-haven.md",
        "name_en": "Hogenakkal: Ancient Kaveri Charnockite Gorge, Whirlpool Rapids & Parisal Coracle Haven",
        "name_ta": "ஒகேனக்கல் - பண்டைய காவேரி பாறைப் பள்ளத்தாக்கு, நீர்ச்சுழல் அருவிகள் மற்றும் பரிசல் துறைத் தளம்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Dramatic charnockite river gorge on the Dharmapuri border where the Kaveri plunges from the Mysore plateau into the Tamil plains, renowned for centuries as the supreme center of split-bamboo Parisal coracle building, turbulent canyon navigation, and gorge cast-net fishing.",
        "summary_ta": "தருமபுரி மாவட்டத்தில் காவேரி ஆறு மலைப் பள்ளத்தாக்குகளில் பாய்ந்திறங்கும் ஒகேனக்கல்: நூற்றாண்டுகளாகத் தொடரும் மூங்கில் பரிசல் கட்டுமானம், சுழல் நீர் துடுப்புக் கலை மற்றும் ஆற்று மீன்பிடித் தளம்.",
        "sources": [
            "Dharmapuri & Salem District Gazetteers",
            "Hornell Indian Coracles and Basket Boats",
            "Geological Survey of India: Hogenakkal Carbonatite & Charnockite Gorge"
        ],
        "content": "# Hogenakkal: Kaveri Gorge & Parisal Coracle Haven\n\nAt Hogenakkal in Dharmapuri district, the Kaveri River drops through a jagged fault-line canyon of Pre-Cambrian charnockite and carbonatite rocks, creating a landscape navigable only by the circular *Parisal* coracle:\n\n**Ecological & Craft Prominence:**\n- **Montane Bamboo Supply**: The surrounding Melagiri and Pennagaram hill forests provide abundant stands of dense, thick-walled *Dendrocalamus strictus* bamboo required for weaving impact-resistant coracle frames.\n- **Canyon Whirlpool Mastery**: Below the main falls, the river funnels through deep, swirling rock cauldrons where keeled boats cannot operate; generation after generation of local *parisal* boatmen have navigated these eddies to harvest large river carp and catfish and to ferry forest produce between the Dharmapuri and Kollegal banks."
    },
    {
        "slug": "concept-bamboo-culm-silicification-flexural-modulus-and-water-seasoning",
        "category": "concept",
        "file": "concept-bamboo-culm-silicification-flexural-modulus-and-water-seasoning.md",
        "name_en": "Dendrocalamus Culm Silicification, Flexural Elasticity & Running-Water Starch Leaching",
        "name_ta": "கல்மூங்கில் சிலிக்கா படிக உறை, வளைவு நெகிழ்வுத்தன்மை மற்றும் ஓடுநீர் மாவுச்சத்து நீக்கப் பதப்படுத்துதல்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Botanical mechanics of coracle bamboo (Dendrocalamus strictus): vascular bundle density gradient across the culm wall, epidermal silica phytoliths resisting abrasion, and submerging split laths in running river water to leach soluble sugars that attract powder-post beetles (Dinoderus).",
        "summary_ta": "பரிசல் செய்யப் பயன்படும் கல்மூங்கிலின் தாவரவியல் வலிமை: வெளிப்புறத் தோலில் உள்ள சிலிக்கா கடினத்தன்மை, வளைந்தாலும் முறியாத நார் அமைப்பு மற்றும் ஆற்று நீரில் ஊறவைத்து வண்டு அரிக்காமல் பாதுகாக்கும் முறை.",
        "sources": [
            "Bamboo Structural Mechanics & Anatomy Studies",
            "Indian Forest Records: Dendrocalamus strictus",
            "Traditional Bamboo Preservation in South India"
        ],
        "content": "# Bamboo Culm Mechanics & Running-Water Seasoning\n\nThe structural longevity of a *Parisal* basket frame under daily immersion and boulder impacts relies on the functional gradient anatomy of solid hill bamboo (*Kal-Moongil*, *Dendrocalamus strictus*):\n\n**Biomechanical Properties:**\n- **Functionally Graded Culm Wall**: Sclerenchyma fiber bundles are densely packed toward the outer epidermis and sparser toward the inner pith, giving split laths an exceptional strength-to-weight ratio and allowing tight bending radii when the outer siliceous rind faces outward.\n- **Running-Water Starch Leaching**: Freshly cut bamboo parenchyma cells contain soluble starch and disaccharides that attract wood-boring *Dinoderus* powder-post beetles. Coracle builders submerge freshly split culms in flowing river water for 2 to 4 weeks, leaching out soluble carbohydrates and leaving a rot- and borer-resistant lignocellulose lattice."
    },
    {
        "slug": "artifact-flat-bottomed-kaveri-padagu-ferry-barges-and-bamboo-pole-punts",
        "category": "artifact",
        "file": "artifact-flat-bottomed-kaveri-padagu-ferry-barges-and-bamboo-pole-punts.md",
        "name_en": "Flat-Bottomed River Padagu Barges, Iron-Shod Bamboo Punt Poles & Cattle Ferry Decks",
        "name_ta": "தட்டை அடிப்பாக ஆற்றுப் படகுகள், இரும்புப் பூண் கட்டிய மூங்கில் கழிகள் மற்றும் கால்நடைத் தோணிகள்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 1950,
        "thinai": "marutham",
        "summary_en": "Complementary heavy river craft of the lower alluvial Kaveri and Coleroon plains: wide flat-bottomed planked barges (padagu / thoni) with raked prows for embarking bullock carts and temple elephants, propelled across sandy shoals by iron-shod bamboo punt poles (kazhi).",
        "summary_ta": "காவேரி மற்றும் கொள்ளிடத்தின் சமவெளிப் பகுதிகளில் மாட்டு வண்டிகளையும் யானைகளையும் கரையேற்றப் பயன்பட்ட தட்டை அடிப்பாகப் பெரும் படகுகள் மற்றும் இரும்புப் பூண் பொருத்திய உந்து கழிகள்.",
        "sources": [
            "Trichinopoly & Tanjore District Gazetteers",
            "Hornell Water Transport",
            "Chola & Nayak River Crossing Epigraphy"
        ],
        "content": "# Flat-Bottomed River Padagu Barges & Punt Poles\n\nWhere the Kaveri emerges from rocky gorges into the wide, sandy alluvial plains of Tiruchirappalli and Thanjavur, circular coracles were complemented by heavy planked river barges (*Padagu* or *Perun-Thoni*):\n\n**Vessel & Propulsion Design:**\n- **Raked-Prow Flat Hulls**: Built of thick *marudhu* (*Terminalia arjuna*) or teak planks with a flat, keel-less floor and wide, gently sloping bow and stern ramps, allowing loaded bullock carts, horses, and palanquins to walk directly aboard from shallow sandbars.\n- **Iron-Shod Punt Poles (*Kazhi*)**: In braided channels of $1-3\\text{ m}$ depth, teams of two to four boatmen walked along narrow side gunwales planting long solid bamboo poles tipped with forked iron shoes (*pootu-kazhi*) into the sandy riverbed to walk the heavy barge upstream against the current."
    }
]

EDGES = [
    [
        "text-sangam-and-historical-accounts-of-ambhi-punai-and-kaveri-coracles",
        "documents",
        "artifact-parisal-bamboo-hull-wooden-sculling-paddles-and-coracle-cast-nets",
        "material_culture",
        "Sangam to Colonial Era",
        "Literary and historical accounts document bamboo river floats and hide-covered circular coracles on the Kaveri.",
        "Ahananuru & Buchanan"
    ],
    [
        "concept-parisal-paraboloid-buoyancy-shallow-draft-and-eddy-stability",
        "governs",
        "technology-split-bamboo-hexagonal-lattice-weaving-and-hide-pitch-waterproofing",
        "material_culture",
        "Iron Age to Modern Era",
        "Paraboloid displacement physics and keel-less eddy stability govern the circular dome geometry of the Parisal.",
        "Hornell Water Transport"
    ],
    [
        "concept-bamboo-culm-silicification-flexural-modulus-and-water-seasoning",
        "enables",
        "technology-split-bamboo-hexagonal-lattice-weaving-and-hide-pitch-waterproofing",
        "material_culture",
        "Iron Age to Modern Era",
        "Water-leached Dendrocalamus strictus culms provide flexible, borer-resistant laths for interlacing coracle frames.",
        "Indian Forest Records"
    ],
    [
        "technology-split-bamboo-hexagonal-lattice-weaving-and-hide-pitch-waterproofing",
        "fabricates",
        "artifact-parisal-bamboo-hull-wooden-sculling-paddles-and-coracle-cast-nets",
        "material_culture",
        "Iron Age to Modern Era",
        "Radial bamboo weaving and waterproof hide/pitch sheathing produce portable Parisal hulls.",
        "Hornell Indian Coracles"
    ],
    [
        "technology-single-paddle-sculling-figure-eight-draw-stroke-and-gorge-ferrying",
        "propels",
        "artifact-parisal-bamboo-hull-wooden-sculling-paddles-and-coracle-cast-nets",
        "material_culture",
        "Iron Age to Modern Era",
        "Figure-eight bow sculling with a single thuduppu paddle pulls the circular coracle forward without spinning.",
        "Kaveri Navigation Ethnography"
    ],
    [
        "concept-thoni-thurai-stone-ford-hydraulics-and-seasonal-flood-ferry-routes",
        "guides",
        "technology-single-paddle-sculling-figure-eight-draw-stroke-and-gorge-ferrying",
        "material_culture",
        "Sangam to Modern Era",
        "Slack-water eddy siting and diagonal drift offsets guide cross-current ferry trajectories between stone ghats.",
        "Coimbatore District Gazetteer"
    ],
    [
        "institution-odaikkarar-ferrymen-guilds-and-royal-thurai-toll-charters",
        "maintains",
        "concept-thoni-thurai-stone-ford-hydraulics-and-seasonal-flood-ferry-routes",
        "material_culture",
        "Medieval to Colonial Era",
        "Hereditary Odaikkarar ferrymen guilds operated thoni-thurai stone ghats under village manyam and chathiram charters.",
        "South Indian Inscriptions"
    ],
    [
        "place-hogenakkal-ancient-kaveri-gorge-parisal-coracle-haven",
        "hosts",
        "technology-split-bamboo-hexagonal-lattice-weaving-and-hide-pitch-waterproofing",
        "material_culture",
        "Iron Age to Modern Era",
        "Hogenakkal canyon on the upper Kaveri is the premier center of bamboo Parisal construction and whirlpool navigation.",
        "Dharmapuri Gazetteer"
    ],
    [
        "institution-odaikkarar-ferrymen-guilds-and-royal-thurai-toll-charters",
        "operates",
        "artifact-flat-bottomed-kaveri-padagu-ferry-barges-and-bamboo-pole-punts",
        "material_culture",
        "Sangam to Modern Era",
        "Ferrymen corporations operated flat-bottomed padagu barges alongside coracles to carry carts and livestock across wide plains.",
        "Trichinopoly Gazetteer"
    ],
    [
        "text-sangam-and-historical-accounts-of-ambhi-punai-and-kaveri-coracles",
        "celebrates",
        "place-hogenakkal-ancient-kaveri-gorge-parisal-coracle-haven",
        "material_culture",
        "Sangam to Colonial Era",
        "Historical accounts of Kaveri gorge crossings highlight the rugged canyon waters navigated by circular coracles.",
        "Salem District Manual"
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
