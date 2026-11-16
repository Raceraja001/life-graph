#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Deep-Sea Shark Hunting, Thimil Outriggers & Harpooning Ballistics
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
        "file": "knowledge/texts/text-natrinai-388-verses-on-deep-sea-shark-hunting-and-harpooning.md",
        "slug": "text-natrinai-388-verses-on-deep-sea-shark-hunting-and-harpooning",
        "category": "text",
        "name_en": "Natrinai 388: Classical Sangam Verses on Deep-Sea Shark Hunting & Harpooning Swells",
        "name_ta": "நற்றிணை 388 - பெருங்கடல் சுறா வேட்டை, எறிசுறா மற்றும் பரதவர் பாய்மரத் திமில் இலக்கியப் பாடல்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "neithal",
        "summary_en": "Classical Natrinai poem depicting fearless Parathavar fishermen navigating dark offshore swells in sail-rigged canoes to harpoon massive predatory sharks (kodu-sura).",
        "summary_ta": "காரிருள் கடலில் கொந்தளிக்கும் அலைகளுக்கு நடுவே, பாய்மரத் திமில்களில் சென்று கொடிய சுறாக்களை இரும்புக் கணைகளால் எறிந்து வேட்டையாடும் பரதவர் வீரத்தை விவரிக்கும் நற்றிணைப் பாடல்.",
        "sources": [
            "Natrinai 388",
            "Akananuru 65",
            "Pattinappalai 60-80"
        ],
        "content": "# Natrinai 388: Deep-Sea Shark Hunting & Harpooning Swells\n\nIn *Natrinai* 388, the Sangam poet vividly captures the perilous maritime livelihood of the coastal *Parathavar* community:\n\n> \"The fearless son of the ocean lord, boarding his narrow-keeled *thimil* with white sails billowed by the night wind, breaches the foaming black breakers to track the deep-sea shark (*kodu-sura*)... Balancing upon the surging prow, he hurls the heavy iron-barbed harpoon into the thrashing sea beast.\"\n\nThis classical verse provides invaluable archaeo-ethnographic testimony to ancient Tamil pelagic navigation. The Neithal seafaring guilds did not restrict their fishing to calm lagoons or shallow sandbars; they mounted nocturnal, offshore expeditions into deep pelagic corridors where apex predatory sharks congregated along oceanic trenches and submarine continental shelves."
    },
    {
        "file": "knowledge/concepts/concept-sura-vettai-deep-sea-shark-hunting-and-pelagic-navigation.md",
        "slug": "concept-sura-vettai-deep-sea-shark-hunting-and-pelagic-navigation",
        "category": "concept",
        "name_en": "Sura-Vettai: Pelagic Shark Hunting Strategy, Oceanic Swell Dynamics & Celestial Navigation",
        "name_ta": "சுறா வேட்டை - ஆழ்கடல் வேட்டை உத்திகள், நீரோட்டக் கணிப்பு மற்றும் விண்மீன் வழிசெலுத்தல்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Advanced open-ocean hunting tactics utilizing celestial orientation, tidal current vectors, and bioluminescent sea trails to track pelagic sharks across continental shelf drop-offs.",
        "summary_ta": "விண்மீன்கள் (வெள்ளி, அருந்ததி), பருவக் காற்று திசைகள் மற்றும் ஆழ்கடல் ஒளிரும் தாவரக் குறிப்புகளைக் கொண்டு, கண்டத் திட்டு ஆழங்களில் சுறாக்களைத் தடம் அறிந்து வேட்டையாடும் நுட்பம்.",
        "sources": [
            "Pattinappalai Marine Verses",
            "Periplus of the Erythraean Sea",
            "Traditional Marine Knowledge of Coromandel"
        ],
        "content": "# Sura-Vettai: Pelagic Shark Hunting Strategy & Navigation\n\n*Sura-Vettai* (deep-sea shark hunting) represented the pinnacle of ancient Tamil open-water seamanship, demanding a sophisticated synthesis of oceanography and celestial navigation:\n\n- **Swell Vector Analysis**: Navigators read the rhythm of long-period oceanic swells (*karai-valai*) rolling off the Bay of Bengal, distinguishing between storm-driven chop and steady subsurface drift currents.\n- **Bioluminescence Tracking**: At night, schools of mackerel and hunting sharks disturbed dinoflagellates, leaving phosphorescent green luminous wakes (*kadal-neri*) that guided harpooners directly to their targets.\n- **Sidereal Course Setting**: Helmsmen aligned their prow with key star markers—principally the pole-ward star, *Velli* (Venus), and the *Aru-Meen* (Pleiades) cluster—to maintain offshore bearings beyond the sight of coastal lighthouses (*ilaingu-sudar*).\n- **Fatigue Trolling**: Once struck with a tethered harpoon, the wounded shark was permitted to pull buoyant wooden drogues and inflated animal bladders until exhausted, preventing dangerous capsizes during boarding."
    },
    {
        "file": "knowledge/technologies/technology-thimil-boat-design-and-heavy-surf-hull-stabilization.md",
        "slug": "technology-thimil-boat-design-and-heavy-surf-hull-stabilization",
        "category": "technology",
        "name_en": "Thimil Craft Architecture: Heavy-Surf Breaker Hydrodynamics & Stitched Plank Stability",
        "name_ta": "திமில் படகு வடிவமைப்பு - கொந்தளிக்கும் கடல் அலை தாங்கும் நீர்மவியல், தைக்கப்பட்ட மரப்பலகை மற்றும் மிதவைத் தொழில்நுட்பம்",
        "era": "Iron Age to Medieval Era",
        "year_start": -600,
        "year_end": 1400,
        "thinai": "neithal",
        "summary_en": "Hydrodynamic naval design of narrow-hulled thimil watercraft built with flexible coir stitching and wild jackwood to safely breach turbulent coastal surf and absorb oceanic shear stresses.",
        "summary_ta": "ஆயிலிய மரப்பலகைகளைத் தேங்காய் நார்க் கயிறுகளால் தைத்து உருவாக்கப்பட்ட, கொந்தளிக்கும் கரைக் கடலின் பிரம்மாண்ட அலைகளைக் கிழித்துச் செல்லும் மீள்தன்மை கொண்ட திமில் படகு.",
        "sources": [
            "Silappadikaram Kadal-Aadukathai",
            "Hornell: The Boats of the Ganges and Tamil Coast",
            "National Institute of Oceanography Reports"
        ],
        "content": "# Thimil Craft Architecture: Surf Hydrodynamics & Stitched Hull\n\nThe *thimil* was the quintessential deep-sea vessel of ancient Tamil coastal harpooners:\n\n- **Flexible Stitched-Plank Construction**: Crafted from resilient, rot-resistant wild jackwood (*aani-maram* / *Artocarpus hirsutus*), the hull planks were joined entirely without rigid iron spikes. Instead, planks were drilled and sewn with dense coir cords (*thengai-naar*) soaked in bitumen and tree dammar.\n- **Elastic Shock Absorption**: The stitched construction granted the hull dynamic flex, enabling it to absorb violent pounding from rolling beach breakers without springing leaks or snapping along stringers.\n- **Cambered Bow Sheer**: A high, sweeping prow cut through high surf, preventing swamping when punching through the shore break.\n- **Hydrodynamic Narrow Beam**: The vessel's lean beam minimized drag, allowing swift acceleration powered by triangular pandanus-mat sails (*kadi-paai*) and rhythmic double-bladed oars (*thudappu*)."
    },
    {
        "file": "knowledge/artifacts/artifact-kodum-thoondil-forged-iron-shark-hooks-and-bronze-barbs.md",
        "slug": "artifact-kodum-thoondil-forged-iron-shark-hooks-and-bronze-barbs",
        "category": "artifact",
        "name_en": "Kodum-Thoondil: Heavy Forged Iron Shark Hooks, Bronze Barbs & Multi-Link Traces",
        "name_ta": "கொடும் தூண்டில் - பெருஞ்சுறா பிடிக்கும் கனரக இரும்புத் தூண்டில், வெண்கலக் கொழு மற்றும் சங்கிலித் தொடர்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Massive hand-forged wootz iron fishing hooks with recurved penetrating points, barbed shanks, and wrought iron chain leaders engineered to withstand razor-sharp shark dentition.",
        "summary_ta": "சுறாக்களின் கூரிய பற்களால் அறுபடாதவாறு இரும்புச் சங்கிலிகளால் இணைக்கப்பட்ட, கூர்மையான வெண்கலக் கொழு கொண்ட மாபெரும் உருக்கு இரும்புத் தூண்டில்.",
        "sources": [
            "Pattirruppattu 41",
            "Korkai Underwater Excavation Reports",
            "Adichanallur Maritime Metallurgy Artifacts"
        ],
        "content": "# Kodum-Thoondil: Forged Iron Shark Hooks & Chain Traces\n\nCapturing sharks weighing upwards of several hundred kilograms required fishing tackle of extraordinary metallurgical strength:\n\n- **High-Carbon Forged Shanks**: *Kodum-thoondil* hooks were hand-forged by coastal ironsmiths (*kollan*) using carbon-rich crucible iron. Shanks were up to 30 cm in length, with an inward recurve that set deeply into the cartilaginous jaws of pelagic sharks upon strike.\n- **Compound Bronze Barbs**: The piercing tip featured an offset triangular barb cast from high-tin bronze or forged iron, preventing the hook from shaking loose during violent acrobatics.\n- **Wrought Iron Chain Traces**: To prevent the shark's triangular serrated teeth from severing fibrous lines, the hook was tethered to a 2-meter heavy link iron chain (*thodari*) before attaching to braided coir hawsers.\n- **Bait Rigging**: Baited with whole bonito, ray liver, or rotting beef scraps, the hook drifted in the water column suspended from floating wooden gourds (*kavudhai*)."
    },
    {
        "file": "knowledge/concepts/concept-sura-kombu-and-pal-shark-teeth-weapons-and-bone-harpoon-tips.md",
        "slug": "concept-sura-kombu-and-pal-shark-teeth-weapons-and-bone-harpoon-tips",
        "category": "concept",
        "name_en": "Sura-Kombu: Sawfish Rostra, Serrated Dermal Weapons & Marine Bone Harpoon Barbs",
        "name_ta": "சுறாக் கொம்பு - இரம்பச் சுறா மூக்கு, கூர்மையான பற்கள் கொண்ட போர்க்கருவிகள் மற்றும் கடல் எலும்பு ஈட்டி முனைகள்",
        "era": "Prehistoric to Medieval Era",
        "year_start": -1000,
        "year_end": 1200,
        "thinai": "neithal",
        "summary_en": "Utilitarian and martial repurposing of sawfish rostra (sura-kombu) and fossilized tiger shark teeth as formidable serrated war clubs, daggers, and detachable toggling harpoons.",
        "summary_ta": "வேட்டையாடப்பட்ட வாள்சுறாக்களின் இரம்ப மூக்கு மற்றும் கூரிய பற்களைக் கொண்டு உருவாக்கப்பட்ட அதிபயங்கர போர்க் கதைகள், வாள்கள் மற்றும் பிரியும் எலும்பு ஈட்டி முனைகள்.",
        "sources": [
            "Purananuru 387",
            "Akananuru 210",
            "South Indian Ethno-Archaeological Collections"
        ],
        "content": "# Sura-Kombu: Shark Teeth Weapons & Bone Harpoons\n\nThe byproducts of shark and sawfish hunting were extensively integrated into maritime defense and hunting armaments:\n\n- **Sawfish Rostral Swords**: The elongated, tooth-studded rostrum of the sawfish (*sura-kombu* or *val-sura*) was dried, cured in salt, and fitted with a cord-wrapped timber grip, creating an intimidating natural serrated sword capable of rending flesh and leather armor.\n- **Composite Teeth Daggers**: Shed or harvested teeth of great white and tiger sharks were grooved along their bases, set into hardwood batons, and lashed with sinew and tree resin, producing fearsome multi-toothed war clubs (*thundil-thadi*).\n- **Detachable Bone Harpoon Heads**: Long dorsal spines of stingrays (*thirukkai*) and dense shark cranial bones were ground into needle-sharp barbed toggles. When thrust into target prey, the toggle head detached from the pole, pivoting sideways inside the muscle to prevent withdrawal."
    },
    {
        "file": "knowledge/institutions/institution-valayar-and-neithal-parathavar-deep-sea-hunting-brotherhood.md",
        "slug": "institution-valayar-and-neithal-parathavar-deep-sea-hunting-brotherhood",
        "category": "institution",
        "name_en": "Parathavar & Valayar: Maritime Brotherhood of Deep-Sea Harpooners & Pearl Guilds",
        "name_ta": "பரதவர் மற்றும் வலையர் - ஆழ்கடல் சுறா வேட்டைக்காரர்கள், பாய்மரக் குழு மற்றும் முத்துக்குளிப்புச் சங்கம்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Hereditary maritime clans governing oceanic fisheries, seasonal shark harpooning expeditions, coastal defense levies, and sacred totemic rites honoring the sea goddess Kadal-Deivam.",
        "summary_ta": "கடல் தொழில், சுறா வேட்டைப் பங்கீடு, கடற்கரை காவல் மற்றும் சுறாக் கொம்பு நடுகல் வழிபாடுகளைத் தலைமை தாங்கி நடத்திய பரதவர் மற்றும் வலையர் கூட்டமைப்பு.",
        "sources": [
            "Pattinappalai 120-135",
            "Silappadikaram 5:10-30",
            "Korkai Inscriptions of Pandya Kings"
        ],
        "content": "# Parathavar & Valayar: Deep-Sea Hunting Brotherhood\n\nThe *Parathavar* and *Valayar* formed an autonomous, aristocratic seafaring corporation across coastal Tamilakam:\n\n- **Egalitarian Catch Apportionment**: Shark hunting yields were divided according to ancient maritime customary law (*kadal-pangu*). Specific shares were allocated to the boat owner, the master harpooner (*mudal-eripon*), the rowers, the village elders, and widows of lost seamen.\n- **Sura-Kombu Totemic Shrines**: Before embarking on dangerous monsoon hunts, guilds erected the rostrum of a giant sawfish in the beach sands (*sura-kombu nadu-kal*). Anointed with sandalwood paste and garlanded with water-lilies (*neithal-poo*), it served as an altar invoking protection against ocean typhoons.\n- **Naval Auxiliary Service**: During wartime, the Pandyan and Chola royal fleets conscripted these elite pelagic harpooners as frontline naval marines, exploiting their mastery over swift watercraft and projectile weaponry."
    },
    {
        "file": "knowledge/technologies/technology-sura-pattu-shark-skin-abrasive-rasps-and-leather-tanning.md",
        "slug": "technology-sura-pattu-shark-skin-abrasive-rasps-and-leather-tanning",
        "category": "technology",
        "name_en": "Sura-Pattu Shagreen: Placoid Scale Abrasives, Gemstone Polishing & Royal Sword Grips",
        "name_ta": "சுறாப் பட்டு - சுறாத் தோல் சாணைத் தொழில்நுட்பம், ரத்தினம் தீட்டுதல் மற்றும் வாள் கைப்பிடி உறை",
        "era": "Classical Antiquity to Medieval Era",
        "year_start": -300,
        "year_end": 1500,
        "thinai": "neithal",
        "summary_en": "Curing and utilization of shark skin (shagreen / sura-pattu) with embedded enamel placoid scales as industrial sandpaper for polishing ivory, teakwood, and providing non-slip sword hilts.",
        "summary_ta": "கண்ணாடி போன்ற பற்கள் கொண்ட சுறாத் தோலைச் சீராக்கி, மரவேலை, தந்தம் மற்றும் ரத்தினங்களை மெருகூட்டப் பயன்பட்ட பண்டைய சாணைத் தோல் தொழில்நுட்பம்.",
        "sources": [
            "Nedunalvadai 80",
            "Arthashastra Book II on Mining and Workshops",
            "Tamil Lexicon on Thol-Pani"
        ],
        "content": "# Sura-Pattu Shagreen: Placoid Scale Abrasives & Tanning\n\nShark hide (*sura-thol* or *sura-pattu*) possessed unique microscopic mineral structures that made it an irreplaceable industrial material:\n\n- **Placoid Dermal Denticles**: The outer surface of shark skin is covered with millions of microscopic, enamel-coated tooth-like scales (placoid scales). When dried, this created a resilient, non-clogging abrasive sheet far superior to crushed sand slurry.\n- **Cabinetry & Ivory Lapping**: Guild woodcarvers and ivory sculptors utilized strips of cured shark skin to buff intricate teak brackets, sandalwood temple doors, and conch shell bangles to a silk-smooth finish.\n- **Non-Slip Weapon Hilts**: Royal swordsmiths stretched damp shark skin over wooden hilts and wrapped them with braided silver wire. As it dried, the hide shrank tightly, forming a textured, moisture-impervious grip that never slipped in sweaty, blood-slicked hand-to-hand combat."
    },
    {
        "file": "knowledge/artifacts/artifact-perum-thamban-heavy-coir-anchor-ropes-and-harpoon-tethers.md",
        "slug": "artifact-perum-thamban-heavy-coir-anchor-ropes-and-harpoon-tethers",
        "category": "artifact",
        "name_en": "Perum-Thamban: High-Tensile Coir Anchor Hawsers, Drogue Floats & Harpoon Lines",
        "name_ta": "பெரும் தம்பான் - ஆழ்கடல் நங்கூரக் கயிறு, மிதவைக் குடுக்கை மற்றும் ஈட்டி இழுப்புக் கயிறு",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Four-strand cable-laid marine cordage spun from salted coconut fiber, designed for extreme tensile shock loading during big-game pelagic harpooning and deep anchoring.",
        "summary_ta": "ஆழ்கடல் அலைகளின் விசையையும், துள்ளும் சுறாக்களின் பலத்தையும் தாங்கும் வண்ணம் 4 முறுக்குகளால் திரிக்கப்பட்ட உறுதியான தென்னங்கயிறு.",
        "sources": [
            "Akananuru 240",
            "Silappadikaram Kadal-Aadukathai",
            "Indian Journal of Marine Archaeology"
        ],
        "content": "# Perum-Thamban: High-Tensile Coir Hawsers & Harpoon Lines\n\nHarpooning a thrashing oceanic shark required tether ropes engineered for elastic energy absorption:\n\n- **Cable-Laid Coir Topology**: *Perum-thamban* was spun from select, salt-retted coconut fibers twisted into three primary strands and then laid up together in reverse helix, preventing kinks under sudden, violent tensile jerks.\n- **High Elastic Elongation**: Unlike stiff hemp or cotton, coir ropes can stretch up to 25% without snapping, functioning as a natural shock absorber when a 400-kg shark surges toward the ocean depths.\n- **Buoyant Wooden Drogues**: Harpoon lines were affixed to dried, resin-coated bottle gourds (*kavudhai*) or light buoyant timber billets (*poovaracu*). The hydrodynamic drag of the floats exhausted the shark while keeping the kill buoyant on the surface."
    },
    {
        "file": "knowledge/concepts/concept-sura-ennai-shark-liver-oil-extraction-and-hull-waterproofing.md",
        "slug": "concept-sura-ennai-shark-liver-oil-extraction-and-hull-waterproofing",
        "category": "concept",
        "name_en": "Sura-Ennai: Squalene-Rich Shark Liver Oil Extraction, Hull Pitch & Medicinal Balms",
        "name_ta": "சுறா எண்ணெய் - சுறா கல்லீரல் எண்ணெய் பிரித்தெடுத்தல், படகு மரப் பாதுகாப்பு மற்றும் சித்த மருத்துவத் தைலம்",
        "era": "Classical Antiquity to Modern Era",
        "year_start": -400,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Rendering of massive shark livers to extract vitamin- and squalene-dense marine oil used for waterproofing timber boat hulls, night torch beacons, and preparing Siddha anti-inflammatory ointments.",
        "summary_ta": "சுறாக்களின் கல்லீரலை உருக்கி எடுக்கப்படும் கொழுப்பு எண்ணெய், கப்பல் மரங்களை நீர் மற்றும் பூச்சிகளிடமிருந்து பாதுகாக்கவும், கலங்கரை விளக்க எரிபொருளாகவும் பயன்பட்ட விதம்.",
        "sources": [
            "Agathiyar Gunavagadam",
            "Boga Munivar 7000",
            "Traditional Boat Building Practices of Tamil Nadu"
        ],
        "content": "# Sura-Ennai: Shark Liver Oil Extraction & Technical Applications\n\nThe liver of deep-sea sharks (*sura-eeral*), comprising up to 20% of the creature's total body weight, was a vital industrial and medicinal commodity:\n\n- **Thermal Rendering**: Artisans gently boiled shark livers in earthen cauldrons with seawater, allowing the light, amber-colored squalene oil to float to the top where it was skimmed and filtered through cotton cloths.\n- **Marine Hull Impregnation**: Mixed with crushed dammar resin (*kungiliyam*) and slaked lime, hot shark oil was applied to the outer planks of *thimil* and *kattumaram* craft. The squalene penetrated deep into the wood pores, polymerizing into a durable barrier repelling shipworms (*Teredo navalis*) and marine algae.\n- **Siddha Medicinal Value**: Ancient Siddha physicians prescribed *sura-ennai* as a potent internal tonic for respiratory ailments and formulated it into topical liniments for chronic joint rheumatism and muscular fatigue."
    },
    {
        "file": "knowledge/places/place-poompuhar-ancient-neithal-shark-hunting-haven.md",
        "slug": "place-poompuhar-ancient-neithal-shark-hunting-haven",
        "category": "place",
        "name_en": "Poompuhar: Ancient Neithal Shark Hunting Flotilla, Maritime Haven & Fisher Guild Sanctuary",
        "name_ta": "பூம்புகார் - பண்டைய நெய்தல் சுறா வேட்டைத் துறை, பரதவர் குடியிருப்பு மற்றும் கடல் ஆழ்கலத் தளம்",
        "era": "Iron Age to Medieval Era",
        "year_start": -600,
        "year_end": 1300,
        "thinai": "neithal",
        "summary_en": "The historic Chola river-mouth emporium of Kaveripoompattinam, home to extensive settlements of intrepid deep-sea harpooners, coastal shipyards, and sacred marine shrines.",
        "summary_ta": "காவிரி கடலோடு கலக்கும் முகத்துவாரத்தில் அமைந்த சோழர் துறைமுகம், பரதவர் திமில் படகுக் குழாம்கள் மற்றும் ஆழ்கடல் வேட்டைப் பண்பாட்டின் முதன்மைத் தளம்.",
        "sources": [
            "Pattinappalai 1-40",
            "Silappadikaram Puhar Kandam",
            "Underwater Archaeological Surveys at Poompuhar (NIO)"
        ],
        "content": "# Poompuhar: Ancient Neithal Shark Hunting Haven\n\nLocated where the sacred Kaveri River empties into the Bay of Bengal in Mayiladuthurai district, ancient Poompuhar (Kaveripoompattinam) was the undisputed epicenter of early Chola naval power and deep-sea fisheries:\n\n- **Maruvurpakkam Harpooners Quarters**: The bustling maritime quarter (*Maruvurpakkam*) housed dense settlements of *Parathavar* fishermen, sail-makers, cordage twisters, and iron hook smiths living alongside foreign Yavanas and trans-oceanic merchants.\n- **Surf Beach Shipways**: The long sandy strand of Poompuhar served as an open-air shipyard where hundreds of *thimil* and sewn-plank craft were launched directly through the booming breakers each dusk.\n- **Underwater Archaeological Discoveries**: Marine excavations offshore at Poompuhar by the Archaeological Survey of India (ASI) and NIO have documented submerged brick structures, stone anchors, and lead/iron fishing tackle, verifying classical Sangam depictions of continuous maritime occupation."
    }
]

EDGES = [
    [
        "text-natrinai-388-verses-on-deep-sea-shark-hunting-and-harpooning",
        "DESCRIBES",
        "concept-sura-vettai-deep-sea-shark-hunting-and-pelagic-navigation",
        "core",
        "Sangam Era",
        "Natrinai 388 verses describe pelagic shark hunting expeditions and night swells.",
        "Natrinai 388"
    ],
    [
        "concept-sura-vettai-deep-sea-shark-hunting-and-pelagic-navigation",
        "UTILIZES",
        "technology-thimil-boat-design-and-heavy-surf-hull-stabilization",
        "core",
        "Iron Age to Medieval Era",
        "Deep-sea shark hunters relied on surf-breaching flexible thimil craft.",
        "Silappadikaram Kadal-Aadukathai"
    ],
    [
        "concept-sura-vettai-deep-sea-shark-hunting-and-pelagic-navigation",
        "DEPLOYED",
        "artifact-kodum-thoondil-forged-iron-shark-hooks-and-bronze-barbs",
        "core",
        "Iron Age to Modern Era",
        "Open-ocean shark hunters baited massive recurved wootz iron hooks with chain traces.",
        "Adichanallur Maritime Metallurgy Artifacts"
    ],
    [
        "artifact-kodum-thoondil-forged-iron-shark-hooks-and-bronze-barbs",
        "TETHERED_WITH",
        "artifact-perum-thamban-heavy-coir-anchor-ropes-and-harpoon-tethers",
        "core",
        "Iron Age to Modern Era",
        "Heavy shark hooks were tethered to multi-strand shock-absorbing coir hawsers.",
        "Akananuru 240"
    ],
    [
        "concept-sura-vettai-deep-sea-shark-hunting-and-pelagic-navigation",
        "YIELDED",
        "concept-sura-kombu-and-pal-shark-teeth-weapons-and-bone-harpoon-tips",
        "core",
        "Prehistoric to Medieval Era",
        "Hunted sawfish and sharks yielded serrated bone harpoons and war swords.",
        "Purananuru 387"
    ],
    [
        "concept-sura-vettai-deep-sea-shark-hunting-and-pelagic-navigation",
        "PRODUCED",
        "technology-sura-pattu-shark-skin-abrasive-rasps-and-leather-tanning",
        "core",
        "Classical Antiquity to Medieval Era",
        "Dried shark shagreen provided industrial abrasive sheets and sword hilt wraps.",
        "Nedunalvadai 80"
    ],
    [
        "concept-sura-vettai-deep-sea-shark-hunting-and-pelagic-navigation",
        "EXTRACTED",
        "concept-sura-ennai-shark-liver-oil-extraction-and-hull-waterproofing",
        "core",
        "Classical Antiquity to Modern Era",
        "Shark liver oil was extracted for boat waterproofing and Siddha medicines.",
        "Agathiyar Gunavagadam"
    ],
    [
        "concept-sura-vettai-deep-sea-shark-hunting-and-pelagic-navigation",
        "ORGANIZED_BY",
        "institution-valayar-and-neithal-parathavar-deep-sea-hunting-brotherhood",
        "core",
        "Iron Age to Modern Era",
        "Parathavar and Valayar guilds governed seasonal offshore shark flotillas.",
        "Pattinappalai 120-135"
    ],
    [
        "institution-valayar-and-neithal-parathavar-deep-sea-hunting-brotherhood",
        "BASED_AT",
        "place-poompuhar-ancient-neithal-shark-hunting-haven",
        "core",
        "Iron Age to Medieval Era",
        "Poompuhar served as the premier coastal haven for deep-sea fishing guilds.",
        "Pattinappalai 1-40"
    ],
    [
        "technology-thimil-boat-design-and-heavy-surf-hull-stabilization",
        "LAUNCHED_FROM",
        "place-poompuhar-ancient-neithal-shark-hunting-haven",
        "core",
        "Iron Age to Medieval Era",
        "Thimil fleets breached the heavy beach surf directly from Poompuhar beaches.",
        "Silappadikaram Puhar Kandam"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 36: Ancient Tamil Deep-Sea Shark Hunting, Thimil Outriggers & Harpooning Ballistics...")
    
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

    print(f"Ingestion Complete for Batch 36 Corpus! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
