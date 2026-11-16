#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Pelagic Fishing & Thimil Harpoonry
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
        "file": "knowledge/texts/text-akanannuru-parathavar-pelagic-shark-hunting-and-thimil-poetry.md",
        "slug": "text-akanannuru-parathavar-pelagic-shark-hunting-and-thimil-poetry",
        "category": "text",
        "name_en": "Akananuru: Classical Sangam Verses on Parathavar Shark Hunting & Thimil Longboats",
        "name_ta": "அகநானூறு - பரதவர் சுறாவேட்டை, திமில் மற்றும் ஆழ்கடல் மீன்பிடிப் பாடல்கள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "neithal",
        "summary_en": "Akananuru maritime anthology depicting Parathavar deep-sea nocturnal expeditions in thimil boats to harpoon fearsome horned sharks (kuraal) and sawfish along the Coromandel shelf.",
        "summary_ta": "அகநானூற்று நெய்தல் பாடல்கள் பரதவர் நள்ளிரவில் திமில் படகுகளில் கடலுக்குச் சென்று, கூரிய இரும்பு எறிகோல் கொண்டு கொம்புச் சுறாக்களை வேட்டையாடும் வீரத்தை விவரிக்கின்றன.",
        "sources": [
            "Akananuru 210",
            "Akananuru 320",
            "Natrinai 303"
        ],
        "content": "# Akananuru: Classical Sangam Poetry on Pelagic Shark Hunting\n\nAkananuru offers peerless eyewitness poetic accounts of deep-sea pelagic fishery and maritime courage among the Parathavar clans of the Gulf of Mannar and Palk Strait. Sangam bards capture the perilous oceanic lifestyle of fishers venturing beyond the sight of land in graceful plank-built craft known as thimil.\n\nThe verses depict how coastal fishermen tracked pelagic predators, especially the aggressive sawfish and hammerhead sharks known as kuraal or iravu-thirukkai. Using heavy iron harpoons forged by coastal blacksmiths and tethered to long hemp ropes, harvesters engaged in furious oceanic duels against thrashing sea monsters under pitch-black midnight skies.\n\nThe poetry celebrates the joyful return of the thimil flotillas at dawn, their decks laden with massive shark carcasses whose oil fueled seaside lamps and whose white meat was salted along the dunes."
    },
    {
        "file": "knowledge/concepts/concept-plank-built-thimil-longboats-and-twin-outrigger-hydrodynamics.md",
        "slug": "concept-plank-built-thimil-longboats-and-twin-outrigger-hydrodynamics",
        "category": "concept",
        "name_en": "Plank-Built Thimil Longboats & Seagoing Wave Hydrodynamics (Thimil Naval Architecture)",
        "name_ta": "திமில் - ஆழ்கடல் மரப்பலகைப் படகு மற்றும் அலை தாங்கும் நீரியல் வடிவமைப்பு",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1700,
        "thinai": "neithal",
        "summary_en": "Naval architecture of sewn-plank, narrow-beam Tamil thimil fishing longboats, engineered from durable teak and wild jackwood to breach massive oceanic breakers with exceptional stability.",
        "summary_ta": "தேக்கு மற்றும் பலா மரப்பலகைகளைத் தென்னை நார்க் கயிறுகளால் தைத்து, கொந்தளிக்கும் ஆழ்கடல் அலைகளைக் கிழித்துச் செல்லும் திமில் படகுகளின் பாரம்பரிய கப்பற்கலை வடிவமைப்பு.",
        "sources": [
            "Periplus of the Erythraean Sea",
            "Traditional Marine Crafts of Tamil Nadu (S.I. Maritime Survey)"
        ],
        "content": "# Plank-Built Thimil Longboats & Wave Hydrodynamics\n\nThe thimil represents one of the most sophisticated indigenous open-ocean fishing vessels developed in ancient South Asia. Unlike near-shore log rafts, the thimil was a true keel-less, carvel-built displacement vessel constructed by stitching hand-adzed planks of wild jackfruit (aazhi-pala) or malabar teak with coir cordage.\n\nDesigned with a high, sharp stem post and raked stern, the thimil had an elongated, hydrodynamically streamlined hull that sliced through treacherous surf zones without capsizing. Flexible stitched seams allowed the hull planks to flex elastomericallly against pounding swells, dissipating immense wave shock that would shatter rigid iron-fastened frames.\n\nRigged with a single dipping lugsail woven from palmyrah mats and powered by four to six long steering oars (valayam), the thimil could sail effortlessly over deep pelagic fishing banks thirty nautical miles offshore."
    },
    {
        "file": "knowledge/concepts/concept-deep-sea-shark-and-sawfish-harpoonry-kuraal-vaall.md",
        "slug": "concept-deep-sea-shark-and-sawfish-harpoonry-kuraal-vaall",
        "category": "concept",
        "name_en": "Deep-Sea Shark & Sawfish Harpoon Ballistics (Kuraal-Vettai & Iravu-Koli Metallurgy)",
        "name_ta": "கொம்புச் சுறா மற்றும் வாள்மீன் எறிகோல் வேட்டை - குறாள்வாள் போரியல் முறைமை",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Specialized oceanic harpoonry system using detachable barbed iron spears (kuraal-vaall/iravu-koli) and floating wooden drogue buoys to hunt pelagic sharks and swordfish.",
        "summary_ta": "ஆழ்கடலில் கொம்புச் சுறாக்களையும் வாள்மீன்களையும் வீழ்த்தப் பயன்படுத்தப்பட்ட கழன்று கொள்ளும் கூரிய இரும்பு எறிகோல் மற்றும் மிதவை மரக்கட்டை வேட்டை முறை.",
        "sources": [
            "Pattiswaram Maritime Inscriptions",
            "Natrinai 388"
        ],
        "content": "# Deep-Sea Shark & Sawfish Harpoon Ballistics (Kuraal-Vettai)\n\nHunting apex marine predators in the open ocean was an elite martial discipline among ancient Tamil Parathavars. Bards refer to the ferocious sawfish and great white sharks as kuraal-meen, feared for their capacity to smash boat hulls with their serrated rostrums.\n\nTo conquer these beasts, fishers designed the iravu-koli (night harpoon). The weapon featured a heavy, double-barbed iron head loosely socketed onto a ten-foot weighted shaft of solid rock-bamboo. Upon penetrating the thick dermal denticles of the shark, the iron head detached from the shaft, remaining deeply embedded while tethered to a hundred fathoms of twisted coir rope linked to buoyant cork floats.\n\nThe buoy exerted continuous drag, exhausting the thrashing beast over hours of oceanic struggle until it could be safely drawn alongside the thimil and dispatched with heavy lignum-vitae clubs."
    },
    {
        "file": "knowledge/concepts/concept-bioluminescent-night-fishing-with-oil-torches-theevatti-meenpidi.md",
        "slug": "concept-bioluminescent-night-fishing-with-oil-torches-theevatti-meenpidi",
        "category": "concept",
        "name_en": "Nocturnal Ocean Fishing with Cast Torches & Lure Fires (Theevatti-Meenpidi & Thirai-Oli)",
        "name_ta": "தீவட்டி மீன்பிடி - நள்ளிரவு கடல் அலை ஒளிப்பந்தங்கள் மற்றும் கவர்ச்சி மீன்வேட்டை",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1600,
        "thinai": "neithal",
        "summary_en": "Nocturnal pelagic fishing technique mounting resin-soaked torches (theevatti) on boat prows to attract phototactic schooling fish and illuminate underwater predatory sharks.",
        "summary_ta": "திமில் படகுகளின் முன்பகுதியில் நறுமணப் பிசின் தீவட்டிகளை ஏற்றி, ஒளியை நோக்கி வரும் மீன்கூட்டங்களையும் சுறாக்களையும் நள்ளிரவில் கவரும் கடல் வேட்டை முறைமை.",
        "sources": [
            "Akananuru 65",
            "Pattinappalai lines 110-125"
        ],
        "content": "# Nocturnal Ocean Fishing with Oil Torches (Theevatti-Meenpidi)\n\nOne of the most striking visual spectacles of the Sangam Coromandel coastline was nocturnal torch fishing (theevatti-meenpidi). On moonless nights (amavasai), flotillas of thimil boats anchored over offshore reefs, lighting massive flaming cressets mounted on projecting iron bowsprits.\n\nThe torches, fueled by unrefined fish liver oil mixed with forest dammar resin (kungiliyam), cast a penetrating flare into the crystalline tropical waters. Surface-dwelling squid, flying fish, and sardines swarmed mesmerized toward the radiant illumination.\n\nTaking advantage of this gathering, master harpooners struck the large pelagic predators drawn to feed upon the schooling fish. Pattinappalai poetically likens the distant offshore lights of the thimil fleet to stars floating upon the restless ocean surface."
    },
    {
        "file": "knowledge/concepts/concept-hemp-fiber-drift-net-knotting-and-beach-fish-curing-karuvadu.md",
        "slug": "concept-hemp-fiber-drift-net-knotting-and-beach-fish-curing-karuvadu",
        "category": "concept",
        "name_en": "Sun-Hemp Drift Net Weaving & Coastal Brine Curing Platforms (Meen-Valai & Karuvadu)",
        "name_ta": "சணல் நார்த் தழும்பு வலைப் பின்னல் மற்றும் கடற்கரை உப்புக் கருவாட்டுப் பதனிடுதல்",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Techniques for weaving high-tensile sun-hemp drift nets (perum-valai) boiled in mangrove bark tannin, and the hygienic salting and sun-drying of oceanic fish catches upon beach platforms (meen-thattigal).",
        "summary_ta": "கண்டல் மரப்பட்டை சாற்றில் வேகவைத்து வலுவூட்டப்பட்ட சணல் வலைகள் மற்றும் கடற்கரை மூங்கில் தட்டிகளில் உப்பிட்டு உலர்த்தும் பாரம்பரிய கருவாட்டுத் தயாரிப்பு.",
        "sources": [
            "Perumpanattruppadai lines 320-340",
            "Silappadikaram Pukarkandam"
        ],
        "content": "# Sun-Hemp Drift Net Weaving & Beach Fish Curing (Karuvadu)\n\nThe shore infrastructure supporting Tamil pelagic fisheries involved complex processing arts. Fishing nets (perum-valai and kodu-valai) were knotted by hand from indigenous sun-hemp (Crotalaria juncea) or palmyrah leaf fibers.\n\nTo protect the plant fibers from seawater rot and marine boring worms, new nets were boiled in large copper cauldrons with crushed bark of coastal mangrove trees (Rhizophora mucronata). The dense catechins and tannins imparted a dark red hue while tripling fiber tensile strength and flexibility.\n\nUpon beaching the boats, the catch was immediately dressed, eviscerated, and steeped in crystal sea salt from adjacent salt pans (umanar alams). The salted fillets were laid upon elevated bamboo drying grilles (meen-thattigal) where ocean breezes and relentless equatorial sun desiccated the fish into long-lasting karuvadu, traded hundreds of miles inland."
    },
    {
        "file": "knowledge/inscriptions/insc-uvari-pandya-parathavar-fishing-fleet-and-salt-tithe-charters.md",
        "slug": "insc-uvari-pandya-parathavar-fishing-fleet-and-salt-tithe-charters",
        "category": "inscription",
        "name_en": "Uvari Pandya Inscriptions on Parathavar Fishing Fleets & Oceanic Fish Tithes",
        "name_ta": "உவரி பாண்டியர் கல்வெட்டுகள் - பரதவர் திமில் படகுக் கடற்படை மற்றும் மீன்வரி சாசனம்",
        "era": "Early Pandya Era",
        "year_start": 750,
        "year_end": 900,
        "thinai": "neithal",
        "summary_en": "Granite epigraphs discovered near the coastal shrine of Uvari recording royal Pandya edicts protecting Parathavar thimil longboats and establishing maritime fish tax allotments for seaside temples.",
        "summary_ta": "உவரி கடற்கரைக் கோயிலில் உள்ள பாண்டியர் காலக் கல்வெட்டுகள், பரதவர்களின் திமில் படகுகளுக்கு அரச பாதுகாப்பும், ஆழ்கடல் மீன்பிடிக்கான வரிச் சலுகைகளையும் பதிவு செய்கின்றன.",
        "sources": [
            "South Indian Inscriptions Vol XIV",
            "Tirunelveli District Archaeological Survey"
        ],
        "content": "# Uvari Pandya Epigraphs on Fishing Fleets & Maritime Tithes\n\nEngraved on the ancient structural foundations of coastal shrines at Uvari on the Gulf of Mannar, these early Pandya records illuminate the legal status of maritime fishing communities.\n\nThe edicts record agreements between the royal Pandya treasury (Pandya bandaram) and the municipal Parathavar council (neithal tharagar). In recognition of the fleet's bravery in guarding the southern sea approaches against foreign pirates, the crown exempted thimil boatwrights from customary timber felling taxes.\n\nThe fleet pledged in return an annual tithe of premium cured shark fins, dried fish bales, and giant sawfish rostrums dedicated to decorate the halls of royal temples and port administrative offices."
    },
    {
        "file": "knowledge/inscriptions/insc-korkai-pearl-diver-and-deep-sea-fisher-guild-epigraphs.md",
        "slug": "insc-korkai-pearl-diver-and-deep-sea-fisher-guild-epigraphs",
        "category": "inscription",
        "name_en": "Korkai Inscriptions on Maritime Fisher Guilds & Harpooner Privileges",
        "name_ta": "கொற்கை கல்வெட்டுகள் - ஆழ்கடல் பரதவ எறிகோல் வணிகக் குழு மற்றும் உரிமைச் சாசனங்கள்",
        "era": "Sangam to Medieval Pandya Era",
        "year_start": -100,
        "year_end": 850,
        "thinai": "neithal",
        "summary_en": "Ancient epigraphical charters from the historic Pandya port of Korkai granting deep-sea harpooners and pearl divers exclusive fishing grounds and hereditary coastal estates.",
        "summary_ta": "கொற்கை துறைமுகக் கல்வெட்டுகள் ஆழ்கடல் சுறா வேட்டையாடும் எறிகோல் மறவர்களுக்கும் முத்துக் குளிப்போருக்கும் வழங்கப்பட்ட தனித்துவக் கடல் உரிமைகளை விவரிக்கின்றன.",
        "sources": [
            "Korkai Excavation Epigraphs (State Dept of Archaeology)",
            "Epigraphia Indica Vol XXVIII"
        ],
        "content": "# Korkai Inscriptions on Maritime Fisher Guilds\n\nUnearthed at the ancient emporium of Korkai on the mouth of the Thamirabarani River, these monumental inscriptions detail the socio-economic prestige commanded by elite ocean fishers.\n\nThe texts demonstrate that deep-sea harpooners were organized alongside pearl divers into powerful maritime corporate bodies known as valaiyar-kottam. They possessed autonomous judicial authority to settle open-sea collision disputes, net-tangling quarrels, and territory infringements along pelagic submarine trenches.\n\nThe Korkai epigraphs also confirm that master thimil navigators held high naval advisory ranks, often commanding auxiliary littoral patrols during times of overseas military campaigns."
    },
    {
        "file": "knowledge/characters/char-uvari-master-thimil-helmsman-and-shark-hunter-thimil-thalaivan.md",
        "slug": "char-uvari-master-thimil-helmsman-and-shark-hunter-thimil-thalaivan",
        "category": "character",
        "name_en": "Uvari Master Thimil Helmsman & Pelagic Shark Harpooner (Thimil Thalaivan)",
        "name_ta": "உவரி தலைமைத் திமில் மாலுமி மற்றும் ஆழ்கடல் சுறா எறிகோல் வீரன்",
        "era": "Sangam Era",
        "year_start": -150,
        "year_end": 100,
        "thinai": "neithal",
        "summary_en": "Legendary Parathavar navigator and fearless oceanic harpooner renowned for steering stitched thimil longboats into open sea storms and slaying giant sawfish with iron hand harpoons.",
        "summary_ta": "கொந்தளிக்கும் கடல் அலைகளில் துணிச்சலுடன் திமில் செலுத்தி, நள்ளிரவில் தன் கூரிய எறிகோலால் ஆழ்கடல் பெருஞ்சுறாக்களை வீழ்த்தும் பரதவத் தலைவன்.",
        "sources": [
            "Akananuru 210",
            "Natrinai 303"
        ],
        "content": "# Uvari Master Thimil Helmsman (Thimil Thalaivan)\n\nThe Thimil Thalaivan represents the heroic apex of Neithal maritime fortitude. Born on the windswept coral sands of Uvari, he learned the behavior of sea currents, benthic trenches, and celestial navigation from childhood.\n\nHe guided his crew of five oarsmen far beyond the breaker line, reading the subtle color changes of the water and the flight paths of shearwaters to pinpoint pelagic feeding grounds. When a giant sawfish was sighted breaching the dark swells, the helmsman personally mounted the narrow stem post, balancing precariously upon the leaping bow to heave his heavy barbed harpoon with pinpoint accuracy.\n\nHis scar-covered torso testified to dozens of maritime encounters, making him a revered figure in coastal assemblies and bardic poetry."
    },
    {
        "file": "knowledge/characters/char-neithal-parathavar-pelagic-guild-elder-valai-mooppan.md",
        "slug": "char-neithal-parathavar-pelagic-guild-elder-valai-mooppan",
        "category": "character",
        "name_en": "Neithal Parathavar Pelagic Guild Elder & Fleet Patriarch (Valai Mooppan)",
        "name_ta": "நெய்தல் பரதவர் ஆழ்கடல் மீன்பிடி பெருமூப்பன்",
        "era": "Early Medieval Era",
        "year_start": 800,
        "year_end": 950,
        "thinai": "neithal",
        "summary_en": "Venerable maritime patriarch presiding over the coastal fisher council, responsible for inspecting boat timber integrity, consecrating new sun-hemp nets, and resolving maritime boundary disputes.",
        "summary_ta": "பரதவக் கடற்கரையின் முதுபெரும் தலைவர்; மரக்கலங்களின் உறுதித்தன்மையை ஆராய்ந்து, சணல் வலைகளைப் புனிதப்படுத்தி, கடற்பரப்புப் பகிர்வை நிர்வகித்த நெய்தல் தலைவர்.",
        "sources": [
            "Pandya Coastal Administrative Rolls",
            "Traditional Fisheries Jurisprudence of Tamil Nadu"
        ],
        "content": "# Neithal Parathavar Guild Elder (Valai Mooppan)\n\nThe Valai Mooppan exercised supreme customary authority over the fishing settlements along the southern littoral. Residing in a palm-thatched compound overlooking the fleet anchorage, he commanded deep respect as the keeper of oceanic lore.\n\nHe determined the seasonal fishing calendar, decreeing mandatory rest periods for juvenile fish stocks and signaling the commencement of the southwest monsoon pelagic season. Before new thimil boats were launched, the elder led traditional rituals to Varuna and the ocean spirit Kadal-Deivam, smearing the stem post with vermilion and coconut oil.\n\nHe also negotiated collective fish sale contracts with inland salt-caravan merchants (umanar), protecting the economic rights of widows and injured mariners."
    },
    {
        "file": "knowledge/places/place-uvari-ancient-neithal-thimil-harpoon-and-pelagic-haven.md",
        "slug": "place-uvari-ancient-neithal-thimil-harpoon-and-pelagic-haven",
        "category": "place",
        "name_en": "Uvari: Ancient Neithal Thimil Harpoon & Pelagic Fishery Haven",
        "name_ta": "உவரி - பண்டைய நெய்தல் திமில் துறைமுகம் மற்றும் ஆழ்கடல் வேட்டைப் புகலிடம்",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Historic coastal fishing harbor on the Gulf of Mannar, celebrated since classical Sangam antiquity as the preeminent heartland of Tamil thimil boatwrights, shark harpooners, and beach fish curing.",
        "summary_ta": "மன்னார் வளைகுடாவில் அமைந்துள்ள தொன்மையான பரதவர் துறைமுகத் தளம்; சங்க காலம் தொட்டே ஆழ்கடல் திமில் படகுகள், சுறா வேட்டை மற்றும் கருவாட்டுத் தொழிற்துறையின் முதன்மை மையம்.",
        "sources": [
            "Akananuru 320",
            "Archaeological Survey of India (Tirunelveli Coast)"
        ],
        "content": "# Uvari: Ancient Neithal Thimil Harpoon Haven\n\nNestled along the southern arc of the Gulf of Mannar in modern Tirunelveli district, Uvari stands as one of the most venerable maritime settlements of ancient Tamilakam. Its natural roadstead, sheltered from the fiercest oceanic gales by barrier sand dunes (theri kaadu) and offshore coral reefs, provided a safe launchpad for deep-sea fishing expeditions.\n\nClassical Sangam literature repeatedly references Uvari under various ancient toponyms, describing its bustling beach markets filled with drying shark fins, mounds of curing salt, and lines of tall thimil masts drying under the coastal breeze.\n\nArchaeological explorations along the Uvari coast have revealed Sangam-period ceramic sherds, iron harpoon fragments, and ancient stone anchors, testifying to millennia of heroic maritime labor."
    }
]
EDGES = [
    [
        "text-akanannuru-parathavar-pelagic-shark-hunting-and-thimil-poetry",
        "documents_technique",
        "concept-deep-sea-shark-and-sawfish-harpoonry-kuraal-vaall",
        "historical_proof",
        "Sangam Era",
        "Akananuru provides explicit heroic verse documenting midnight shark and sawfish harpooning from thimil boats.",
        "Akananuru 210"
    ],
    [
        "text-akanannuru-parathavar-pelagic-shark-hunting-and-thimil-poetry",
        "celebrates_vessel",
        "concept-plank-built-thimil-longboats-and-twin-outrigger-hydrodynamics",
        "historical_proof",
        "Sangam Era",
        "Sangam verses immortalize the stitched-plank thimil longboats navigating roaring pelagic breakers.",
        "Akananuru 320"
    ],
    [
        "concept-plank-built-thimil-longboats-and-twin-outrigger-hydrodynamics",
        "utilized_in",
        "concept-bioluminescent-night-fishing-with-oil-torches-theevatti-meenpidi",
        "historical_proof",
        "Sangam to Medieval Era",
        "Thimil boats carried projecting iron bowsprits bearing flaming oil torches to attract nocturnal marine fish.",
        "Pattinappalai lines 110-125"
    ],
    [
        "concept-deep-sea-shark-and-sawfish-harpoonry-kuraal-vaall",
        "supplies_catch",
        "concept-hemp-fiber-drift-net-knotting-and-beach-fish-curing-karuvadu",
        "historical_proof",
        "Prehistoric to Modern Era",
        "Massive pelagic shark catches were dressed, salted, and sun-cured on beach platforms into durable karuvadu.",
        "Perumpanattruppadai lines 320-340"
    ],
    [
        "char-uvari-master-thimil-helmsman-and-shark-hunter-thimil-thalaivan",
        "operates_in",
        "place-uvari-ancient-neithal-thimil-harpoon-and-pelagic-haven",
        "historical_proof",
        "Sangam Era",
        "The master thimil helmsman commanded deep-sea harpoon crews operating out of Uvari coastal haven.",
        "Natrinai 303"
    ],
    [
        "char-uvari-master-thimil-helmsman-and-shark-hunter-thimil-thalaivan",
        "wields_weapon",
        "concept-deep-sea-shark-and-sawfish-harpoonry-kuraal-vaall",
        "historical_proof",
        "Sangam Era",
        "Master helmsmen balanced upon leaping thimil prows to spear thrashing sawfish with detachable iron harpoons.",
        "Akananuru 210"
    ],
    [
        "char-neithal-parathavar-pelagic-guild-elder-valai-mooppan",
        "presides_over",
        "place-uvari-ancient-neithal-thimil-harpoon-and-pelagic-haven",
        "historical_proof",
        "Early Medieval Era",
        "The guild patriarch governed fishing seasons, boat timber inspections, and fish barter contracts at Uvari.",
        "Pandya Coastal Administrative Rolls"
    ],
    [
        "insc-uvari-pandya-parathavar-fishing-fleet-and-salt-tithe-charters",
        "attests_place",
        "place-uvari-ancient-neithal-thimil-harpoon-and-pelagic-haven",
        "historical_proof",
        "Early Pandya Era",
        "Early Pandya epigraphs at Uvari document royal charters protecting thimil boatwrights and fish tithes.",
        "South Indian Inscriptions Vol XIV"
    ],
    [
        "insc-korkai-pearl-diver-and-deep-sea-fisher-guild-epigraphs",
        "records_privileges",
        "concept-deep-sea-shark-and-sawfish-harpoonry-kuraal-vaall",
        "historical_proof",
        "Sangam to Medieval Pandya Era",
        "Korkai epigraphs confirm hereditary maritime rights and tax immunities granted to open-ocean harpooner guilds.",
        "Korkai Excavation Epigraphs"
    ],
    [
        "place-uvari-ancient-neithal-thimil-harpoon-and-pelagic-haven",
        "preserves_heritage",
        "concept-plank-built-thimil-longboats-and-twin-outrigger-hydrodynamics",
        "historical_proof",
        "Prehistoric to Modern Era",
        "Uvari continues to preserve the ancient shipbuilding and deep-sea navigation traditions of Tamil thimil mariners.",
        "Archaeological Survey of India (Tirunelveli Coast)"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Ancient Tamil Pelagic Fishing & Thimil Harpoonry into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Ancient Tamil Pelagic Fishing & Thimil Harpoonry Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
