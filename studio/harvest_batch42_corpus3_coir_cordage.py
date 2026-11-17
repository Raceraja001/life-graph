#!/usr/bin/env python3
"""
Harvester: Batch 42 - Ancient Tamil Coir Cordage, Brackish Lagoon Coconut Fibre Retting & Marine Caulking Engineering
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
        "slug": "text-perumpanarruppadai-and-pattinappalai-on-coir-stitched-ships",
        "category": "text",
        "file": "text-perumpanarruppadai-and-pattinappalai-on-coir-stitched-ships.md",
        "name_en": "Perumpanarruppadai & Pattinappalai Verses on Coir Cordage, Stitched Ships & Ocean Vangams",
        "name_ta": "பெரும்பாணாற்றுப்படை மற்றும் பட்டினப்பாலை தென்னை நார் கயிறு தைத்த நாவாய்கள் பாடல் குறிப்புகள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Classical Sangam poems celebrating the golden coir rope (*kayiru*) spun from sea-soaked coconut husks, used to lash ocean-going vessels (*Kattumaram*, *Vangam*, *Navaai*) that rode towering ocean waves without breaking.",
        "summary_ta": "கடல் நீரில் ஊறவைத்த தென்னை மட்டையிலிருந்து திரிக்கப்பட்ட உறுதியான கயிறுகள் மற்றும் பலகைகளை இணைத்துத் தைத்து கடலில் பாய்ந்தோடிய நாவாய்கள் பற்றிய சங்கப் பாடல்கள்.",
        "sources": [
            "Perumpanarruppadai 315-320",
            "Pattinappalai 170-175",
            "Ahananuru 255",
            "Silappadikaram Kadalaadukathai"
        ],
        "content": "# Perumpanarruppadai & Pattinappalai on Coir-Stitched Ships\n\nThe ocean-going seafaring technology of ancient Tamil Nadu relied critically on the tensile elasticity of natural coconut coir cordage:\n\n**Literary Testimonies:**\n- **Perumpanarruppadai (lines 315-320)**: Describes coastal fishermen's quarters where massive coils of twisted golden coconut fibre rope (*the-kayiru*) hang drying in sea breezes, used to lash outrigger timbers of catamarans and anchor deep-sea vessels.\n- **Pattinappalai (lines 170-175)**: Portrays the harbour of Poompuhar crowded with high-masted ships (*vangam*) whose hulls were sewn together with pitch-coated coir twine, flexing safely across stormy ocean rollers where rigid iron nails would shear.\n- **Periplus Maris Erythraei (Sec. 60)**: Documents Roman merchants observing native Tamil sewn vessels (*madarata*) stitched tightly with local coir yarn."
    },
    {
        "slug": "concept-cocos-nucifera-mesocarp-lignocellulose-and-anaerobic-retting",
        "category": "concept",
        "file": "concept-cocos-nucifera-mesocarp-lignocellulose-and-anaerobic-retting.md",
        "name_en": "Cocos Nucifera Mesocarp Lignocellulose Chemistry & Brackish Lagoon Retting Kinetics",
        "name_ta": "தென்னை மட்டை லிக்னோசெல்லுலோஸ் வேதியியல் மற்றும் உவர்நீர்க் கழிமுக ஊறவைத்தல் இயக்கவியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -1000,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Biochemical structure and retting dynamics of coconut husk (Cocos nucifera): high lignin content (40-45%) rendering fibres rot-resistant in saltwater, anaerobic pectinolytic bacterial biodegradation in tidal backwaters, and hemicellulose dissolution.",
        "summary_ta": "தென்னை மட்டையின் லிக்னின் கட்டமைப்பு: உப்புநீரில் அழுகாத 45% லிக்னின் உள்ளடக்கம், கழிமுக உவர்நீரில் பாக்டீரியாக்கள் மூலம் பெக்டின் சிதைந்து நார் பிரித்தெடுக்கப்படும் உயிரியல் முறை.",
        "sources": [
            "Bioresource Technology Journal",
            "CSIR Central Coir Research Institute Reports",
            "Journal of Applied Polymer Science"
        ],
        "content": "# Cocos Nucifera Mesocarp Lignocellulose & Retting Kinetics\n\nThe fiber extracted from the fibrous mesocarp of the coconut palm possesses biomechanical properties unequaled by any terrestrial plant fiber:\n\n**Biochemical Mechanics:**\n- **Lignin Saturation**: Unlike cotton or flax, coconut coir contains $40-45\\\\%$ lignin alongside $35-40\\\\%$ cellulose. This high lignin-to-cellulose ratio renders the fiber virtually impervious to marine fungal decay and saltwater rot.\n- **Microbial Retting (*Azhukku-Podudhal*)**: Green husks were submerged in shallow saline lagoons for 8 to 10 months. Anaerobic pectinolytic bacteria (*Clostridium* and *Bacillus* strains) broke down the binding pectins and polyphenols without degrading structural cellulose fibers.\n- **Salinity Synergy**: Constant tidal flushing in brackish estuaries removed soluble tannins and prevented stagnant putrefaction, yielding soft, resilient golden-blonde fiber."
    },
    {
        "slug": "technology-manual-beating-spinning-wheel-thiri-and-reverse-ply-cordage",
        "category": "technology",
        "file": "technology-manual-beating-spinning-wheel-thiri-and-reverse-ply-cordage.md",
        "name_en": "Mallet Defibration, Ratchet Spinning Wheel (Thiri) & Reverse Two-Ply Twisting",
        "name_ta": "மர சுத்தியல் மட்டை அடித்தல், ராட்டை சுழல் திரிப்பு மற்றும் இருபுரி எதிர்சுழல் கயிறு முறுக்கு",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "The mechanical sequence of Tamil coir production: manual beating of retted husks with heavy tamarind mallets, iron-toothed combing (carding), reverse two-ply hand twisting, and geared spinning wheel (raattai) cordage fabrication.",
        "summary_ta": "தென்னை நார் பிரித்தல் மற்றும் கயிறு தயாரிக்கும் முறை: ஊறவைத்த மட்டையை மர சுத்தியலால் அடித்து நார் பிரித்தல், தூய்மை செய்தல், மற்றும் ராட்டை கொண்டு இருபுரியாக முறுக்குதல்.",
        "sources": [
            "Traditional Coir Technology Monographs",
            "Indian Journal of Traditional Knowledge",
            "Tamil Marine Artisanship Studies"
        ],
        "content": "# Mallet Defibration & Reverse Two-Ply Cordage\n\nTransforming tangled retted husks into high-tensile marine cordage combined rhythmic manual percussion with rotational kinematics:\n\n**Processing Stages:**\n1. **Mallet Beating (*Kotta-Puli*)**: Retted husks were placed on smooth granite stones and beaten rhythmically with short, dense tamarind-wood clubs to loosen the pith (*coir dust*) from the long structural bristle fibers.\n2. **Hackling & Combing**: Hand-drawn across beds of vertical iron spikes to comb out impurities and align long fibers in parallel hanks.\n3. **Reverse Two-Ply Twisting (*Erattai-Thiri*)**: Spinners fed two continuous strands into rotating whorls turned by a geared wheel (*raattai*), twisting each strand clockwise (Z-twist) while plying them together counter-clockwise (S-twist). This counter-balanced reverse torque prevented unravelling under tension."
    },
    {
        "slug": "artifact-marakkalam-stitched-planks-coir-rigging-and-resin-caulking",
        "category": "artifact",
        "file": "artifact-marakkalam-stitched-planks-coir-rigging-and-resin-caulking.md",
        "name_en": "Marakkalam Stitched Timber Planks, Heavy Coir Rigging & Dammar Tree Resin Caulking",
        "name_ta": "மறைக்கலப் பலகைத் தையல், தடித்த நார் வடங்கள் மற்றும் குங்கிலியப் பிசின் அடைப்பான்",
        "era": "Iron Age to Medieval Era",
        "year_start": -500,
        "year_end": 1400,
        "thinai": "neithal",
        "summary_en": "Diagnostic archaeological and ethnological elements of stitched Tamil marine hulls: drilled anjili and teak hull planks stitched with two-ply coir yarn, heavy hawser anchor ropes (vadams), and caulking mastic of dammar resin (kungiliyam), lime, and fish oil.",
        "summary_ta": "பண்டைய கப்பல் கட்டும் பொருட்கள்: துளைகள் இடப்பட்ட தேக்கு மரப் பலகைகள், தடித்த நார் வடங்கள், மற்றும் நீர் புகாமல் அடைக்கப் பயன்பட்ட குங்கிலியப் பிசின், சுண்ணம் மற்றும் மீன் எண்ணெய் கலவை.",
        "sources": [
            "Underwater Archaeology of Poompuhar",
            "Indian Ocean Stitched Ship Monographs",
            "Marine Archaeology Centre Goa"
        ],
        "content": "# Marakkalam Stitched Timber Planks & Resin Caulking\n\nThe hallmark of the ancient Indian Ocean maritime shipbuilding tradition was the flexible stitched plank construction:\n\n**Material Assemblage:**\n- **Sewn Planks**: Hull planks of wild jack (*Artocarpus hirsutus*) or teak were edge-bored with angled holes at 5–8 cm intervals. High-tensile coir yarn was threaded through the holes over longitudinal coir rolls (*wadding*), drawing the timbers tightly together.\n- **Caulking Mastic (*Kungiliya-Kalappu*)**: A molten formulation of Shorea tree resin (*kungiliyam*), animal tallow or shark liver oil, and fine slaked shell lime was forced into seams and over stitch holes.\n- **Elastic Sea-Keeping**: Unlike rigid iron-fastened hulls that strained and sheared when striking shallow sandy sandbars, coir-stitched hulls flexed with waves, self-healing under hydrostatic pressure."
    },
    {
        "slug": "concept-coir-tensile-strength-saltwater-elongation-and-rot-resistance",
        "category": "concept",
        "file": "concept-coir-tensile-strength-saltwater-elongation-and-rot-resistance.md",
        "name_en": "Coir Fiber Tensile Mechanics, Wet Elongation Elasticity & Saltwater Preservation",
        "name_ta": "தென்னை நார் இழுவிசை இயக்கவியல், ஈரப்பதம் தாங்கும் நெகிழ்வுத்தன்மை மற்றும் உப்புநீர் அழுகாமை",
        "era": "Iron Age to Modern Era",
        "year_start": -1000,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Biophysical mechanics of marine coir rope: ultimate tensile strength (130-175 MPa), high elongation-at-break (up to 30%), energy absorption capacity under ocean swell surge loads, and micro-tannin preservation in hypersaline water.",
        "summary_ta": "தென்னை நார் கயிற்றின் இயற்பியல் வலிமை: 175 MPa வரையிலான இழுவிசை, 30% நீளும் நெகிழ்வுத்தன்மை, கடல் அலைகளின் திடீர் அழுத்தத்தைத் தாங்கும் திறன் மற்றும் அழுகாமை.",
        "sources": [
            "Polymer Testing: Marine Natural Fibres",
            "Textile Research Journal",
            "CSIR Central Coir Research Institute"
        ],
        "content": "# Coir Fiber Tensile Mechanics & Elasticity\n\nMarine ropes must endure continuous cyclic shock loads without snapping:\n\n**Mechanical Performance Profile:**\n- **High Elongation-at-Break**: Coir fibers can stretch by 25–30% before rupture—more than double that of Manila hemp or cotton ($10-12\\%$). This extreme extensibility absorbs violent dynamic shock waves from storm swells without parting anchor lines.\n- **Hydrophobic Resistance**: Because of dense external lignified cuticles, coir does not absorb excessive internal water, maintaining lightweight buoyancy and preventing waterlogged sinking.\n- **Tensile Longevity**: While hemp and sisal rot within weeks when exposed to continuous seawater immersion, coir cordage retains $80\\\\%$ of its original tensile strength even after two years of complete oceanic deployment."
    },
    {
        "slug": "institution-kayittru-valaiignar-and-vanga-marakkar-guild-of-coir-spinners",
        "category": "institution",
        "file": "institution-kayittru-valaiignar-and-vanga-marakkar-guild-of-coir-spinners.md",
        "name_en": "Kayittru-Valaiignar & Vanga-Marakkar Guild: Coir Spinners & Shipwright Corporation",
        "name_ta": "கயிற்று வினைஞர் மற்றும் வங்க மரைக்காயர் சபை: கயிறு தயாரிப்பாளர் மற்றும் கப்பல் கட்டும் பெருமன்றம்",
        "era": "Sangam to Chola Era",
        "year_start": -400,
        "year_end": 1300,
        "thinai": "neithal",
        "summary_en": "The maritime corporate artisan guild uniting coastal coconut planters, lagoon retting specialists, female rope twisters, and master shipwrights: standardizing cordage gauges, supplying royal naval dockyards, and enforcing maritime trade monopolies.",
        "summary_ta": "தென்னை விவசாயம், மட்டை ஊறவைத்தல், கயிறு திரிப்போர் மற்றும் கப்பல் கட்டும் கலைஞர்களை ஒருங்கிணைத்த கடற்கரை தொழில் சங்கம்: சோழர் கடற்படைக்கு கயிறுகள் வழங்கல் மற்றும் ஏற்றுமதி.",
        "sources": [
            "South Indian Epigraphy: Marine Guild Charters",
            "Nagapattinam Port Inscriptions",
            "Maritime History of South India"
        ],
        "content": "# Kayittru-Valaiignar & Vanga-Marakkar Guild\n\nCoir rope manufacturing was organized as an integrated industrial economy linking coastal agricultural groves with deep-sea shipyards:\n\n**Guild Functions:**\n- **Lagoon Commons Regulation**: Managed zoning of brackish estuary retting trenches (*azhukku-padukal*), preventing contamination of freshwater wells and establishing fair soaking rotations.\n- **Cordage Standards**: Certified rope thickness classifications ranging from thin stitching twines (*nool*) to massive 10-inch anchor hawsers (*perum-vadam*).\n- **Chola Naval Supply Contracts**: Fulfilled massive imperial quotas for running and standing rigging supplied to naval shipyards constructing war flotillas for expeditions to Sri Lanka and Srivijaya."
    },
    {
        "slug": "technology-marine-caulking-resin-pitch-melting-and-seam-packing",
        "category": "technology",
        "file": "technology-marine-caulking-resin-pitch-melting-and-seam-packing.md",
        "name_en": "Marine Caulking Pyrotechnics, Dammar Pitch Melting & Estuarine Seam Packing",
        "name_ta": "கப்பல் இடுக்கு அடைப்பு உத்திகள், குங்கிலியப் பிசின் உருக்குதல் மற்றும் கயிறு அடைக்கும் நுட்பம்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "The pyrotechnical and mechanical process of waterproofing ocean-going hulls: boiling tree resin (kungiliyam) with seed oils to create elastic pitch, hammering loose coir tow into timber seams with caulking chisels, and sealing joints with hot pitch.",
        "summary_ta": "கப்பல் பலகை இடுக்குகளில் நீர் புகாமல் அடைக்கும் தொழில்நுட்பம்: மரப் பிசினை எண்ணெயுடன் சேர்த்து கொதிக்க வைத்து பசையாக்குதல், நார் அடைப்பான்களை உளி கொண்டு பலகை இடுக்குகளில் அடித்தல்.",
        "sources": [
            "Ethnoarchaeology of Stitched Boats",
            "Journal of Maritime Archaeology",
            "Indian Ocean Shipbuilding Studies"
        ],
        "content": "# Marine Caulking Pyrotechnics & Seam Packing\n\nA stitched vessel's watertight integrity depended on the chemical and mechanical synergy of fibrous packing and hydrophobic sealants:\n\n**Caulking Protocols:**\n1. **Tow Preparation**: Soft, carded coir fibers (*tow*) were rolled into long loose strands and soaked in boiled seed oils.\n2. **Chisel Ramming**: Using blunt-nosed iron caulking irons (*kalam-uli*) and wooden mallets, caulkers drove the oiled coir tow deeply into the seams between hull timbers, packing it until rock-hard.\n3. **Hot Pitch Sealing**: Dammar resin (*kungiliyam*) melted with shark liver oil and pulverized lime was poured while boiling over the stitched seams. As it cooled, it formed a flexible, rubbery waterproof barrier that expanded when wet, perfectly neutralizing seam seepage."
    },
    {
        "slug": "place-kottaipattinam-ancient-coir-cordage-haven",
        "category": "place",
        "file": "place-kottaipattinam-ancient-coir-cordage-haven.md",
        "name_en": "Kottaipattinam: Ancient Coir Cordage Haven, Palk Strait Lagoon & Stitched Ship Citadel",
        "name_ta": "கோட்டைப்பட்டினம் - பண்டைய கயிற்றுத் தளம், பால்க் ஜலசந்தி உப்பங்கழி மற்றும் நாவாய் கட்டும் மையம்",
        "era": "Iron Age to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Historic port haven on the Palk Strait in Pudukkottai district, celebrated across millennia for its vast brackish coconut retting lagoons, high-tensile coir rope spinning bazaars, and traditional boatbuilding yards crafting ocean catamarans.",
        "summary_ta": "புதுக்கோட்டை மாவட்டத்தில் பால்க் ஜலசந்திக் கரையில் அமைந்துள்ள புகழ்பெற்ற கடற்கரைத் துறைமுகம்: உவர்நீர் தென்னை மட்டை ஊறவைக்கும் உப்பங்கழிகள், கயிறு தயாரிப்பு மற்றும் நாவாய் கட்டும் தொழிற்கூடம்.",
        "sources": [
            "Pudukkottai District Gazetteer",
            "Palk Bay Maritime Heritage Surveys",
            "Studies in Tamil Maritime Architecture"
        ],
        "content": "# Kottaipattinam: Ancient Coir Cordage Haven\n\nSheltered along the shallow, calm waters of Palk Bay, Kottaipattinam was a primary engine of Tamil maritime rigging and cordage production:\n\n**Maritime Prominence:**\n- Its protected estuarine backwaters provided ideal, non-turbulent brackish retting beds where millions of coconut husks were soaked in anaerobic tidal mud for months.\n- Kottaipattinam served as the primary supply depot for coir hawsers, anchor cables, and stitched planking cordage utilized by Chola and Pandyan merchant flotillas crossing to Jaffna, Kedah, and Malacca.\n- Even today, hereditary boatbuilders (*Marakkalars*) maintain the living technology of stitched hull lashing and coir spinning in unbroken continuity."
    },
    {
        "slug": "concept-catamaran-tied-log-hydrodynamics-and-breaking-surf-resilience",
        "category": "concept",
        "file": "concept-catamaran-tied-log-hydrodynamics-and-breaking-surf-resilience.md",
        "name_en": "Kattumaram Tied-Log Hydrodynamics, Flexible Wave Absorption & Breaking Surf Resilience",
        "name_ta": "கட்டுமரம் கயிறு கட்டுக் கட்டமைப்பு, அலை நெகிழ்வு நீர் இயக்கவியல் மற்றும் கரை அலை தாங்கும் திறன்",
        "era": "Iron Age to Modern Era",
        "year_start": -1000,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Hydrodynamic and structural mechanics of the indigenous Tamil raft (Kattumaram - 'tied logs'): buoyant Albizia and Melia logs lashed together exclusively with coir rope, flexing without capsizing across high-energy Coromandel breaking surf.",
        "summary_ta": "பாரம்பரிய கட்டுமரத்தின் நீரியக்கவியல் மற்றும் வடிவமைப்பு: மரக் கட்டைகளை இரும்பு ஆணிகள் இன்றி தென்னை நார் கயிறுகளால் மட்டுமே கட்டி, கொந்தளிக்கும் கடலோரப் பேரலைகளை நெகிழ்ந்து கடக்கும் அற்புத நுட்பம்.",
        "sources": [
            "Journal of Coastal Research",
            "Traditional Watercraft of the Coromandel Coast",
            "UNESCO Intangible Maritime Heritage"
        ],
        "content": "# Kattumaram Tied-Log Hydrodynamics & Surf Resilience\n\nThe *Kattumaram* (literally 'tied logs') is the most hydrodynamic and unsinkable surf-craft invented in maritime history:\n\n**Structural Mechanics:**\n- **Flexible Log Articulation**: Three to five shaped logs of lightweight *Albizia stipulata* or *Melia dubia* are lashed together exclusively with thick coir ropes. Because the logs are tied rather than rigidly joined, the craft flexes over breaking waves, dissipating massive wave shock energy through slight articulation.\n- **Natural Drainage**: Seawater crashing over the raft instantly drains through gaps between the logs, preventing the vessel from ever becoming swamped or waterlogged.\n- **Breaking Surf Survival**: When returning through violent shallow coastal surf barriers where rigid wooden or fiberglass boats capsize and shatter, the Kattumaram flexes harmlessly over sandbars."
    },
    {
        "slug": "artifact-the-kayiru-coir-hawsers-anchor-cables-and-braided-rigging",
        "category": "artifact",
        "file": "artifact-the-kayiru-coir-hawsers-anchor-cables-and-braided-rigging.md",
        "name_en": "The-Kayiru Golden Coir Hawsers, Braided Rigging & Stone Anchor Lashings",
        "name_ta": "தேங்காய்க் கயிறு தடித்த வடங்கள், கப்பல் பாய்மரக் கயிறுகள் மற்றும் கல் நங்கூரக் கட்டுகள்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Material repertoire of ancient Tamil marine cordage: three-strand coiled hawsers (vadam), tarred standing rigging shrouds, flexible braided sheets for cotton sails, and heavy stone anchor lashings (nanguram-kayiru).",
        "summary_ta": "பண்டைய கப்பல் கயிற்றுத் தொகுப்பு: முப்புரி தடித்த நங்கூர வடங்கள், பாய்மரக் கயிறுகள், துணிப் பாய்களைக் கட்டுப்படுத்தும் கயிறுகள் மற்றும் பெரும் கல் நங்கூரங்களை இணைக்கும் வடங்கள்.",
        "sources": [
            "National Institute of Oceanography Marine Archaeology",
            "Kaveripoompattinam Port Excavations",
            "Maritime Museum Cochin Collections"
        ],
        "content": "# The-Kayiru Coir Hawsers & Stone Anchor Lashings\n\nArchaeological dives off Poompuhar, Tranquebar, and Dwarka have recovered preserved coir cordage associated with ancient granite anchors:\n\n**Diagnostic Artifact Repertoire:**\n- **Three-Strand Anchor Hawsers (*Perum-Vadam*)**: Massive rope assemblies measuring 8 to 15 cm in diameter, capable of securing multi-ton merchant vessels against open-ocean gales.\n- **Granite Anchor Lashings**: Heavy Mediterranean-style and Indo-Arab grooved stone anchor stocks were pierced through central flukes and lashed with pitch-treated coir cables that withstood friction against jagged coral reefs.\n- **Braided Running Rigging (*Paai-Kayiru*)**: Flexible, supple ropes that passed through wooden pulley sheaves without jamming, hoisting heavy woven cotton sails."
    }
]

EDGES = [
    [
        "text-perumpanarruppadai-and-pattinappalai-on-coir-stitched-ships",
        "celebrates",
        "technology-manual-beating-spinning-wheel-thiri-and-reverse-ply-cordage",
        "material_culture",
        "Sangam Era",
        "Sangam poetry celebrates the spinning of golden coconut fibre cordage used to rig sea vessels.",
        "Perumpanarruppadai 315-320"
    ],
    [
        "concept-cocos-nucifera-mesocarp-lignocellulose-and-anaerobic-retting",
        "enables",
        "technology-manual-beating-spinning-wheel-thiri-and-reverse-ply-cordage",
        "material_culture",
        "Iron Age to Modern Era",
        "Anaerobic microbial retting dissolves binding pectins without degrading rot-resistant lignin fibres.",
        "Bioresource Technology"
    ],
    [
        "technology-manual-beating-spinning-wheel-thiri-and-reverse-ply-cordage",
        "produces",
        "artifact-the-kayiru-coir-hawsers-anchor-cables-and-braided-rigging",
        "material_culture",
        "Iron Age to Modern Era",
        "Mallet beating and reverse-ply twisting produce heavy anchor hawsers and marine rigging.",
        "Traditional Coir Technology"
    ],
    [
        "technology-manual-beating-spinning-wheel-thiri-and-reverse-ply-cordage",
        "sews",
        "artifact-marakkalam-stitched-planks-coir-rigging-and-resin-caulking",
        "material_culture",
        "Iron Age to Medieval Era",
        "Two-ply coir yarn is threaded through drilled timber planks to construct stitched ship hulls.",
        "Stitched Ship Monographs"
    ],
    [
        "concept-coir-tensile-strength-saltwater-elongation-and-rot-resistance",
        "protects",
        "artifact-marakkalam-stitched-planks-coir-rigging-and-resin-caulking",
        "material_culture",
        "Iron Age to Modern Era",
        "High tensile strength and 30% wet elongation elasticity protect hull timbers from wave impact fractures.",
        "Polymer Testing"
    ],
    [
        "institution-kayittru-valaiignar-and-vanga-marakkar-guild-of-coir-spinners",
        "manages",
        "place-kottaipattinam-ancient-coir-cordage-haven",
        "material_culture",
        "Sangam to Chola Era",
        "Coir spinners and shipwright guilds governed retting lagoons and cordage workshops at Kottaipattinam.",
        "Marine Guild Charters"
    ],
    [
        "place-kottaipattinam-ancient-coir-cordage-haven",
        "hosts",
        "technology-manual-beating-spinning-wheel-thiri-and-reverse-ply-cordage",
        "material_culture",
        "Iron Age to Modern Era",
        "Kottaipattinam estuarine lagoons hosted extensive coir defibration and spinning operations.",
        "Pudukkottai Gazetteer"
    ],
    [
        "technology-marine-caulking-resin-pitch-melting-and-seam-packing",
        "waterproofs",
        "artifact-marakkalam-stitched-planks-coir-rigging-and-resin-caulking",
        "material_culture",
        "Iron Age to Modern Era",
        "Dammar tree resin and fish oil pitch melted over rammed coir tow seals timber joints completely.",
        "Journal of Maritime Archaeology"
    ],
    [
        "concept-catamaran-tied-log-hydrodynamics-and-breaking-surf-resilience",
        "embodies",
        "technology-manual-beating-spinning-wheel-thiri-and-reverse-ply-cordage",
        "material_culture",
        "Iron Age to Modern Era",
        "The Kattumaram raft relies exclusively on flexible coir cordage to articulate buoyant logs over breaking surf.",
        "Journal of Coastal Research"
    ],
    [
        "text-perumpanarruppadai-and-pattinappalai-on-coir-stitched-ships",
        "documents",
        "place-kottaipattinam-ancient-coir-cordage-haven",
        "material_culture",
        "Sangam Era",
        "Sangam literature documents the great stitched ship havens and coir craft workshops along the Palk Bay.",
        "Pattinappalai 170"
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
            emb = get_embedding(ch["content"])
            cur.execute("""
                INSERT INTO rag_chunks (node_slug, shelf, language, title, content, source_ref, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                slug,
                f"shelf-{d['category']}s",
                ch["language"],
                ch["title"],
                ch["content"],
                d["sources"][0] if d["sources"] else "Oral Tradition",
                emb,
            ))
        print(f"Embedded 2 chunks for: {slug}")
    conn.commit()

    cur.close()
    conn.close()
    print("=== Harvester Complete! ===")

if __name__ == "__main__":
    main()
