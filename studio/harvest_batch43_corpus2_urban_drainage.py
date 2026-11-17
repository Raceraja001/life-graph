#!/usr/bin/env python3
"""
Harvester: Batch 43 - Ancient Tamil Terracotta Ring Wells, Sluice Cisterns & Urban Subterranean Drainage
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
        "slug": "text-maduraikanchi-and-nedunalvaadai-on-brick-drains-and-water-cisterns",
        "category": "text",
        "file": "text-maduraikanchi-and-nedunalvaadai-on-brick-drains-and-water-cisterns.md",
        "name_en": "Maduraikanchi & Nedunalvaadai Verses on Subterranean Brick Drains, Ring Wells & Urban Hydraulics",
        "name_ta": "மதுரைக்காஞ்சி மற்றும் நெடுநல்வாடை சுடுமண் உறை கிணறு மற்றும் செங்கல் வடிகால் பாடல் குறிப்புகள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Sangam literary descriptions of urban civil engineering in Pandyan capitals: paved avenues with covered brick storm drains (kazhivu-neer vaikkal), terracotta ring wells (urai-kinaru) providing clean filtered water, and private bathing cisterns.",
        "summary_ta": "சங்க கால நகரக் கட்டடக் கலை மற்றும் நீரியல்: செங்கற்களால் கட்டப்பட்ட மூடிய நிலத்தடி சாக்கடை வடிகால்கள், சுடுமண் வளைய உறை கிணறுகள் மற்றும் குளியல் தொட்டிகள் பற்றிய மதுரைக்காஞ்சிப் பாடல்கள்.",
        "sources": [
            "Maduraikanchi 355-365",
            "Nedunalvaadai 80-90",
            "Pattinappalai 140-145",
            "Keezhadi Archaeological Literary Correlations"
        ],
        "content": "# Maduraikanchi & Nedunalvaadai on Urban Drainage\n\nSangam poetic texts provide rich documentary evidence of planned urban sanitation and hydraulic infrastructure:\n\n**Literary Testimonies:**\n- **Maduraikanchi (lines 355-365)**: Describes the imperial capital Madurai with its broad streets designed with subterranean brick storm drainage ducts (*kazhivu-neer vaikkal*) that channeled household runoff safely away from living quarters into moat ditches.\n- **Nedunalvaadai (lines 80-90)**: Depicts high-walled mansions equipped with burnt terracotta downspouts and tiled roof drainages (*neer-thotti*) discharging rainwater into paved filtration courtyard cisterns.\n- **Pattinappalai (lines 140-145)**: Celebrates the port of Poompuhar where deep cylindrical terracotta ring wells (*urai-kinaru*) tapped coastal fresh groundwater lenses without collapsing in loose beach sands."
    },
    {
        "slug": "concept-soil-mechanics-ring-caisson-structural-engineering-and-aquifer-filtration",
        "category": "concept",
        "file": "concept-soil-mechanics-ring-caisson-structural-engineering-and-aquifer-filtration.md",
        "name_en": "Soil Mechanics, Terracotta Ring Caisson Hydrodynamics & Alluvial Aquifer Filtration",
        "name_ta": "மண் இயக்கவியல், சுடுமண் உறை உட்செலுத்து கட்டமைப்பு மற்றும் வண்டல் நீர் ஊற்று வடிகட்டுதல்",
        "era": "Iron Age to Modern Era",
        "year_start": -1000,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Civil engineering principles of ancient Tamil terracotta ring wells (urai-kinaru): modular interlocking cylindrical caissons resisting lateral earth pressure, self-sinking excavation mechanics in unconsolidated alluvial sands, and natural bottom gravel filtration.",
        "summary_ta": "சுடுமண் உறை கிணறுகளின் சிவில் என்ஜினியரிங் நுட்பம்: பக்கவாட்டு மண் அழுத்தத்தைத் தாங்கும் வளைய வடிவ கட்டமைப்பு, வண்டல் மணலில் எளிதாக இறங்கும் முறை மற்றும் நன்னீர் வடிகட்டல்.",
        "sources": [
            "Geotechnical Engineering of Ancient Wells",
            "Archaeological Survey of India Technical Memoirs",
            "Keezhadi Hydrogeological Reports"
        ],
        "content": "# Soil Mechanics & Terracotta Ring Caisson Engineering\n\nThe invention of stacked terracotta ring caissons (*Urai-Kinaru*) enabled ancient Tamils to sink deep wells in unstable sandy alluvium:\n\n**Geotechnical Principles:**\n- **Lateral Earth Pressure Resistance**: The arch geometry of cylindrical ceramic rings distributes horizontal soil stress evenly in pure compression, preventing sand caving that destroys timber or unlined pits.\n- **Caisson Sinking Method**: A ring of 80–100 cm diameter was placed on the ground, and soil was scooped from within its interior; as earth was removed, the heavy ceramic cylinder sank under gravity. Successive interlocking rings were added on top until the unconfined alluvial water table was reached.\n- **Sediment-Free Upflow**: The bottom of the well was packed with river pebbles and coarse quartz sand, creating a natural upward filtration barrier that arrested sand boiling while yielding crystal-clear water."
    },
    {
        "slug": "technology-burnt-brick-drainage-vaults-socket-spigot-terracotta-piping",
        "category": "technology",
        "file": "technology-burnt-brick-drainage-vaults-socket-spigot-terracotta-piping.md",
        "name_en": "Burnt-Brick Covered Drainage Vaults, Interlocking Socket-Spigot Terracotta Pipes & Sand Traps",
        "name_ta": "சுட்ட செங்கல் மூடிய வடிகால் நிலவறைகள், செருகும் சுடுமண் குழாய்கள் மற்றும் மணல் வடிகட்டித் தொட்டிகள்",
        "era": "Iron Age to Sangam Era",
        "year_start": -600,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "The civil hydraulic infrastructure of Sangam urban settlements: high-fired rectangular burnt bricks laid in lime mortar forming covered underground drainage channels, interlocking socket-and-spigot terracotta pipes, and stepped sand-trap settling basins.",
        "summary_ta": "சங்க கால நகரக் கழிவுநீர் மேலாண்மை நுட்பம்: சுண்ணாம்பு காரை கொண்டு கட்டப்பட்ட மூடிய செங்கல் வடிகால்கள், ஒன்றோடு ஒன்று பொருந்தும் சுடுமண் குழாய் வரிசைகள் மற்றும் வண்டல் வடிகட்டும் தொட்டிகள்.",
        "sources": [
            "Keezhadi Archaeological Excavation Reports (TNSDA)",
            "Kaveripoompattinam Civil Engineering Memoirs",
            "Uraiyur Excavation Reports"
        ],
        "content": "# Burnt-Brick Drainage Vaults & Interlocking Terracotta Piping\n\nExcavations at Keezhadi, Arikamedu, and Kaveripoompattinam demonstrate extraordinary urban hydraulic sophistication:\n\n**Engineering Sequence:**\n1. **Interlocking Pipe Conduits**: Wheel-thrown cylindrical terracotta pipes (15–20 cm diameter, 45–60 cm length) featured flared bell sockets on one end and tapered spigots on the other. Fitted together and sealed with clay-lime mastic, they formed leak-proof subterranean water pipelines.\n2. **Brick-Lined Covered Drains**: Trunk sewer lines were constructed using kiln-fired bricks (standard Sangam ratio 1:2:4, typically $36 \\times 18 \\times 6\\text{ cm}$) laid in stepped courses and capped with flat stone slabs or brick lintels.\n3. **Silt Traps (*Manal-Thotti*)**: Settling cisterns placed at junctions allowed heavy suspended solids to precipitate, preventing pipe clogs before greywater exited into natural lagoons."
    },
    {
        "slug": "artifact-terracotta-well-rings-spigot-drain-pipes-and-soakage-jars",
        "category": "artifact",
        "file": "artifact-terracotta-well-rings-spigot-drain-pipes-and-soakage-jars.md",
        "name_en": "Flanged Terracotta Well Rings, Socket Drain Pipes & Stacked Soakage Jars",
        "name_ta": "விளிம்புடைய சுடுமண் கிணற்று உறைகள், செருகு வடிகால் குழாய்கள் மற்றும் துளை உறிஞ்சுப் பானைகள்",
        "era": "Iron Age to Sangam Era",
        "year_start": -600,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Excavated ceramic hydraulic artifacts of early Tamil urbanization: wheel-thrown earthenware well rings with interlocking flanges, cylindrical drain pipes with slip glaze, and vertically stacked perforated soakage jars (kuzhi-paanai) packed with charcoal and broken potsherds.",
        "summary_ta": "அகழ்வாய்வுப் பொருட்கள்: ஒன்றோடொன்று பூட்டிக்கொள்ளும் விளிம்புகளுடைய சுடுமண் கிணற்று உறைகள், கழிவுநீர் குழாய்கள் மற்றும் கரியும் ஓடுகளும் நிரப்பப்பட்ட செங்குத்து உறிஞ்சுப் பானைகள்.",
        "sources": [
            "Keezhadi Excavation Catalog",
            "Arikamedu Archaeological Artifacts",
            "Tamil Nadu State Archaeology Department"
        ],
        "content": "# Terracotta Well Rings, Drain Pipes & Soakage Jars\n\nThe physical components of ancient Tamil urban sanitation are among the most durable ceramic artifacts recovered:\n\n**Diagnostic Artifact Repertoire:**\n- **Terracotta Well Rings (*Urai*)**: Robust earthenware cylinders (thickness 3–5 cm, height 25–35 cm, diameter 70–90 cm) displaying grooved rims designed to seat snugly into the ring below.\n- **Bell-and-Spigot Pipes**: High-fired reddish-buff pipes with wheel-turned concentric ribbing on the outer surface to anchor mortar adhesion.\n- **Soakage Pits (*Urinji-Paanai*)**: Deep vertical shafts formed by cutting out the bases of three to five giant earthen jars placed one atop another, functioning as decentralized household greywater soakaways."
    },
    {
        "slug": "concept-hydraulic-gradient-gravity-flow-and-manning-roughness-kinetics",
        "category": "concept",
        "file": "concept-hydraulic-gradient-gravity-flow-and-manning-roughness-kinetics.md",
        "name_en": "Hydraulic Gradient Head-Loss, Gravity Drainage Kinetics & Sediment Self-Cleansing",
        "name_ta": "நீரியல் சாய்வு அழுத்தம், ஈர்ப்பு விசை வடிகால் இயக்கவியல் மற்றும் வண்டல் தானியங்கு தூய்மை",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Hydraulic flow principles engineered into ancient Tamil drainage conduits: uniform 1:100 to 1:200 bed slopes maintaining gravity velocity above the critical self-cleansing velocity (0.6 m/s) to prevent silt accumulation, and smooth ceramic boundary roughness.",
        "summary_ta": "வடிகால் கால்வாய்களின் நீரியக்கவியல் கணக்கீடு: வண்டல் படியாமல் இருக்க 1:100 சரிவு அமைத்தல், விநாடிக்கு 0.6 மீட்டர் சுய தூய்மை வேகத்தை பராமரித்தல் மற்றும் உராய்வுக் குறைப்பு.",
        "sources": [
            "Open Channel Hydraulics of Ancient Urbanisms",
            "Civil Engineering Historical Transactions",
            "Journal of Hydraulic Engineering"
        ],
        "content": "# Hydraulic Gradient Kinetics & Self-Cleansing Flows\n\nAncient Tamil civil engineers designed subterranean drains with sophisticated knowledge of open-channel gravity kinetics:\n\n**Hydraulic Calculations:**\n- **Bed Slope Optimization**: Brick conduits excavated at Keezhadi feature consistent longitudinal slopes between $0.5\\\\%$ and $1.0\\\\%$ (1 in 100).\n- **Self-Cleansing Velocity**: According to open channel hydraulics, flow velocities must exceed $0.6\\\\text{ m/s}$ during household discharges to transport organic suspended solids and prevent sewer sedimentation.\n- **Roughness Minimization**: Smooth lime-washed interior surfaces and dense ceramic pipe walls minimized the Manning roughness coefficient ($n \\\\approx 0.012$), maximizing volumetric discharge capacity during torrential monsoon downpours."
    },
    {
        "slug": "institution-ur-manram-and-kuzhu-corporation-of-civic-sanitation-masters",
        "category": "institution",
        "file": "institution-ur-manram-and-kuzhu-corporation-of-civic-sanitation-masters.md",
        "name_en": "Ur-Manram & Vaikkal-Kuzhu Corporation: Municipal Assemblies, Sanitation Inspectors & Ditch Wardens",
        "name_ta": "ஊர் மன்றம் மற்றும் வாய்க்கால் குழு: நகராட்சி சபை, சுகாதார ஆய்வாளர் மற்றும் வடிகால் வாரிய பெருமன்றம்",
        "era": "Sangam to Chola Era",
        "year_start": -400,
        "year_end": 1300,
        "thinai": "marutham",
        "summary_en": "The civic administrative bodies of Tamil towns and cities: municipal assemblies (Ur-Manram) and specialized sanitation committees (Vaikkal-Kuzhu / Thotta-Variyam) that enforced drainage easements, penalized sewer tampering, and dredged public channels.",
        "summary_ta": "பண்டைய நகரங்களின் சுகாதார மற்றும் வடிகால் மேலாண்மை சபை: தெரு வடிகால் பராமரிப்பு, பொது கிணறுகளின் பாதுகாப்பு மற்றும் கழிவுநீர் அடைப்பு நீக்கும் பணிகளை நிர்வகித்த ஊர் மன்றம்.",
        "sources": [
            "Uttiramerur Inscriptional Committee Charters",
            "Keezhadi Civic Inscriptions",
            "South Indian Urban History"
        ],
        "content": "# Ur-Manram & Vaikkal-Kuzhu Municipal Assemblies\n\nUrban sanitation in ancient Tamil society was an institutionalized communal responsibility:\n\n**Municipal Mandates:**\n- **Drainage Easements (*Vaikkal-Urimai*)**: City codes strictly forbade property owners from blocking subterranean conduits or redirecting foul wastewater into freshwater supply channels.\n- **Annual Silt Desilting (*Kuzhi-Vettu*)**: Communities levied collective labor or cash assessments to fund annual pre-monsoon clearing of trunk sewers and ring well silt traps.\n- **Public Well Sanctuaries**: Well precincts were paved and enclosed with low brick parapets to prevent surface storm wash from contaminating drinking aquifers."
    },
    {
        "slug": "technology-brick-corbelling-lime-plaster-waterproofing-cisterns",
        "category": "technology",
        "file": "technology-brick-corbelling-lime-plaster-waterproofing-cisterns.md",
        "name_en": "Brick Corbel Vaulting, Hydraulic Lime Plaster Waterproofing & Settling Tanks",
        "name_ta": "செங்கல் அடுக்கு கவிகைக் கட்டடம், நீரியல் சுண்ணாம்பு காரை பூச்சு மற்றும் நீர் தேக்கத் தொட்டிகள்",
        "era": "Iron Age to Sangam Era",
        "year_start": -600,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Construction engineering of Sangam waterproof cisterns and conduits: corbelled brick arches, calcined seashell lime mortar mixed with jaggery and river sand (hydraulic mortar), and multi-layered burnished waterproof plaster linings.",
        "summary_ta": "நீர்க்கசிவற்ற செங்கல் தொட்டிகள் கட்டும் முறை: செங்கற்களை அடுக்கி கவிகை அமைத்தல், சிப்பி சுண்ணம் மற்றும் வெல்லக் கரைசல் கலந்த காரை பூசுதல் மற்றும் நீர் புகா பூச்சு.",
        "sources": [
            "Ancient Indian Building Materials",
            "TNSDA Technical Engineering Bulletins",
            "Archaeometry of South Indian Mortars"
        ],
        "content": "# Brick Corbel Vaulting & Waterproof Lime Plasters\n\nThe longevity of ancient Tamil water cisterns and drains stems from specialized hydraulic mortar chemistry:\n\n**Material Engineering:**\n1. **Hydraulic Shell-Lime Mortar**: Mortar was prepared by calcining sea shells (*chunnambu*), blending the slaked lime with fine quartz river sand and an organic ferment of jaggery (*vellam*) and terminalia bark water (*kadukkai*).\n2. **Corbelled Architecture**: Wide subterranean drains were spanned using corbelled brick courses stepped inward incrementally until meeting at a central capstone, avoiding wooden supports that would rot in damp sewers.\n3. **Multi-Coat Plastering**: Cistern walls received three successive coats of fine lime plaster, hand-burnished with smooth quartz pebbles to achieve an impervious, glassy hydraulic seal."
    },
    {
        "slug": "place-manalur-ancient-vaigai-urban-drainage-haven",
        "category": "place",
        "file": "place-manalur-ancient-vaigai-urban-drainage-haven.md",
        "name_en": "Manalur: Ancient Vaigai Urban Drainage Haven, Brick Sanitation Citadels & Ring Well Cluster",
        "name_ta": "மணலூர் - பண்டைய வைகை நகர வடிகால் தளம், செங்கல் கழிவுநீர் கால்வாய்கள் மற்றும் உறை கிணற்றுப் பெருநகரம்",
        "era": "Iron Age to Sangam Era",
        "year_start": -600,
        "year_end": 400,
        "thinai": "marutham",
        "summary_en": "Historic archaeological site adjacent to Keezhadi on the Vaigai River in Sivaganga/Madurai district, celebrated for dense clusters of terracotta ring wells, interconnected covered brick drainage arteries, and paved bath platforms of the early Sangam civilization.",
        "summary_ta": "சிவகங்கை/மதுரை மாவட்டத்தில் வைகை ஆற்றங்கரையில் கீழடிக்கு அருகே அமைந்துள்ள தொல்லியல் தளம்: சங்க கால சுடுமண் உறை கிணறுகள், செங்கல் வடிகால்கள் மற்றும் குளியல் தளங்களின் வரலாற்று மையம்.",
        "sources": [
            "Keezhadi Cluster Excavation Reports (TNSDA)",
            "Vaigai Valley Archaeological Surveys",
            "Madurai District Archaeological Atlas"
        ],
        "content": "# Manalur: Ancient Vaigai Urban Drainage Haven\n\nManalur, forming the core urban sprawl of the greater Keezhadi metropolitan cluster, provides unprecedented physical evidence of planned Sangam sanitation:\n\n**Archaeological Discoveries:**\n- Excavation trenches revealed deeply stratified domestic quarters featuring in-situ terracotta ring wells stacked 15–18 rings deep, penetrating into the pristine Vaigai subterranean aquifer.\n- Intricate brick-lined drainage networks connected adjacent residential structures to central trunk conduits that discharged into ancient riverine silt channels.\n- Paved brick platforms associated with terracotta drain pipes illustrate individual private bathroom architecture integrated into municipal wastewater management."
    },
    {
        "slug": "concept-groundwater-hydrology-recharge-and-subsurface-water-tables",
        "category": "concept",
        "file": "concept-groundwater-hydrology-recharge-and-subsurface-water-tables.md",
        "name_en": "Groundwater Hydrology, Subsurface Alluvial Recharge & Unconfined Water Tables",
        "name_ta": "நிலத்தடி நீர் நீரியல், வண்டல்மண் ஊடுருவல் மற்றும் நிலத்தடி நீர்மட்ட சமநிலை",
        "era": "Iron Age to Modern Era",
        "year_start": -1000,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Hydrogeological dynamics of the Vaigai and Kaveri alluvial floodplains: permeable sandy aquifers enabling rapid monsoon infiltration, seasonal water-table fluctuations, and sustainable shallow well extraction without drawdown depletion.",
        "summary_ta": "வைகை மற்றும் காவேரி ஆற்றுப்படுகை நிலத்தடி நீர் சூழலியல்: மழைக்கால நீர் ஊடுருவல், மணல் அடுக்கு நீர் சமநிலை மற்றும் வற்றாத நன்னீர் ஊற்றுகளின் இயக்கவியல்.",
        "sources": [
            "Central Ground Water Board: Alluvial Aquifers of Tamil Nadu",
            "Journal of Hydrology",
            "Hydrogeology of South Indian River Basins"
        ],
        "content": "# Groundwater Hydrology & Subsurface Water Tables\n\nThe flourishing of dense Sangam urban centers along river corridors was sustained by rich unconfined alluvial aquifers:\n\n**Hydrogeological Dynamics:**\n- **Alluvial Permeability**: Coarse riverbed sands and gravel layers display hydraulic conductivity ($K$) values of $10^{-3}$ to $10^{-4}\\text{ m/s}$, enabling swift subsurface water movement from the active riverbed into surrounding urban water tables.\n- **Natural Filtration**: As river floodwaters seeped horizontally through 100–300 meters of fine silty sand, microbial pathogens and suspended sediments were naturally filtered out before reaching domestic ring wells.\n- **Equilibrium Sinks**: Shallow ring wells ($3-6\\text{ m}$ depth) extracted only seasonal water table surpluses, allowing rapid recharge during the Northeast monsoon."
    },
    {
        "slug": "artifact-terracotta-funnels-spouts-and-drainage-elbow-joints",
        "category": "artifact",
        "file": "artifact-terracotta-funnels-spouts-and-drainage-elbow-joints.md",
        "name_en": "Terracotta Drainage Funnels, Curved Elbow Joints & Perforated Silt Strainers",
        "name_ta": "சுடுமண் புனல்கள், வளைந்த முழங்கை மூட்டுகள் மற்றும் துளையிடப்பட்ட வண்டல் வடிகட்டிகள்",
        "era": "Iron Age to Sangam Era",
        "year_start": -600,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Specialized plumbing fittings excavated in Sangam urban sites: wheel-turned terracotta 90-degree and 45-degree angled elbow pipes, funnel-shaped roof collectors, and perforated ceramic strainers inserted at drainage inlets to block debris.",
        "summary_ta": "சங்க கால சிறப்பு பிளம்பிங் உபகரணங்கள்: 90 டிகிரி வளைந்த சுடுமண் முழங்கைக் குழாய்கள், கூரை நீர் சேகரிக்கும் புனல்கள் மற்றும் கழிவுநீர் அடைப்பைத் தடுக்கும் துளைத் தட்டுகள்.",
        "sources": [
            "Keezhadi Specialized Ceramic Catalog",
            "Indian Archaeology Reviews",
            "Bulletin of the Madras Museum"
        ],
        "content": "# Terracotta Drainage Funnels & Elbow Joints\n\nThe sophistication of ancient Tamil plumbing extended to specialized angled ceramic pipe fittings:\n\n**Fittings Typology:**\n- **Right-Angled Elbows (*Valaivu-Kuzhai*)**: Seamless wheel-thrown 90-degree curved pipes engineered to redirect subterranean drains around domestic foundation walls without turbulence.\n- **Roof Drain Funnels**: Broad flaring ceramic hoppers installed beneath roof eaves to funnel torrential monsoon rainwater down vertical wall pipes.\n- **Perforated Inlet Grates**: Circular terracotta discs perforated with small holes placed over household drains to prevent food waste and cloth scraps from entering the subterranean pipe network."
    }
]

EDGES = [
    [
        "text-maduraikanchi-and-nedunalvaadai-on-brick-drains-and-water-cisterns",
        "evidences",
        "technology-burnt-brick-drainage-vaults-socket-spigot-terracotta-piping",
        "material_culture",
        "Sangam Era",
        "Sangam poetry describes covered brick drainage ducts and terracotta ring wells in Pandyan capitals.",
        "Maduraikanchi 355"
    ],
    [
        "concept-soil-mechanics-ring-caisson-structural-engineering-and-aquifer-filtration",
        "governs",
        "technology-burnt-brick-drainage-vaults-socket-spigot-terracotta-piping",
        "material_culture",
        "Iron Age to Modern Era",
        "Lateral earth pressure resistance dictates the cylindrical geometry of terracotta caissons and brick vaults.",
        "Geotechnical Engineering Studies"
    ],
    [
        "technology-burnt-brick-drainage-vaults-socket-spigot-terracotta-piping",
        "manufactures",
        "artifact-terracotta-well-rings-spigot-drain-pipes-and-soakage-jars",
        "material_culture",
        "Iron Age to Sangam Era",
        "High-temperature ceramic manufacture produces flanged well rings, drain pipes, and soakage jars.",
        "Keezhadi Reports"
    ],
    [
        "concept-hydraulic-gradient-gravity-flow-and-manning-roughness-kinetics",
        "optimizes",
        "technology-burnt-brick-drainage-vaults-socket-spigot-terracotta-piping",
        "material_culture",
        "Iron Age to Modern Era",
        "Hydraulic slope gradients and self-cleansing velocity prevent sediment clogging in brick drains.",
        "Open Channel Hydraulics"
    ],
    [
        "institution-ur-manram-and-kuzhu-corporation-of-civic-sanitation-masters",
        "maintains",
        "place-manalur-ancient-vaigai-urban-drainage-haven",
        "material_culture",
        "Sangam to Chola Era",
        "Municipal assemblies and ditch committees maintained municipal brick drains and ring wells in Manalur.",
        "Uttiramerur Charters"
    ],
    [
        "place-manalur-ancient-vaigai-urban-drainage-haven",
        "hosts",
        "technology-burnt-brick-drainage-vaults-socket-spigot-terracotta-piping",
        "material_culture",
        "Iron Age to Sangam Era",
        "Manalur excavations along the Vaigai reveal dense networks of covered brick drains and ring wells.",
        "TNSDA Excavations"
    ],
    [
        "technology-brick-corbelling-lime-plaster-waterproofing-cisterns",
        "waterproofs",
        "artifact-terracotta-well-rings-spigot-drain-pipes-and-soakage-jars",
        "material_culture",
        "Iron Age to Sangam Era",
        "Hydraulic shell-lime plaster and corbelled brick vaulting create durable waterproof cisterns and conduits.",
        "Ancient Building Materials"
    ],
    [
        "concept-groundwater-hydrology-recharge-and-subsurface-water-tables",
        "replenishes",
        "artifact-terracotta-well-rings-spigot-drain-pipes-and-soakage-jars",
        "material_culture",
        "Iron Age to Modern Era",
        "Permeable sandy alluvial aquifers constantly replenish fresh drinking water in terracotta ring wells.",
        "Central Ground Water Board"
    ],
    [
        "technology-burnt-brick-drainage-vaults-socket-spigot-terracotta-piping",
        "incorporates",
        "artifact-terracotta-funnels-spouts-and-drainage-elbow-joints",
        "material_culture",
        "Iron Age to Sangam Era",
        "Subterranean drainage lines incorporate curved elbow joints, funnels, and perforated strainers.",
        "Keezhadi Catalog"
    ],
    [
        "text-maduraikanchi-and-nedunalvaadai-on-brick-drains-and-water-cisterns",
        "celebrates",
        "place-manalur-ancient-vaigai-urban-drainage-haven",
        "material_culture",
        "Sangam Era",
        "Sangam literature celebrates the hygienic urban architecture of Pandyan riverside settlements like Manalur.",
        "Nedunalvaadai 80"
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
        print(f"Embedded {len(chunks)} chunks for: {slug}")
    conn.commit()

    cur.close()
    conn.close()
    print("=== Harvester Complete! ===")

if __name__ == "__main__":
    main()
