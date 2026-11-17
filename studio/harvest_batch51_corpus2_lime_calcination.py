#!/usr/bin/env python3
"""
Harvester: Batch 51 - Ancient Tamil Seashell & Kankar Lime Calcination, Chunnambu-Kalavasal Kilns, Slaking Kinetics & Sudhai Stucco Sculpting
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
        "slug": "text-sangam-literature-on-ven-sudhai-white-lime-mansions-and-stucco-palaces",
        "category": "text",
        "file": "text-sangam-literature-on-ven-sudhai-white-lime-mansions-and-stucco-palaces.md",
        "name_en": "Sangam Literary References to Ven-Sudhai White Lime-Plastered Mansions & Stucco Terraces",
        "name_ta": "சங்க இலக்கியங்களில் வெண்சுதை மாடங்கள், நிலா முற்றம் மற்றும் சுண்ணாம்புச் சாந்துக் குறிப்புகள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Classical Tamil poetic accounts in Pattinappalai, Nedunalvadai, Maduraikanchi, Perumpanarruppadai, and Purananuru describing multi-storied burnt-brick mansions coated with dazzling silver-white seashell lime plaster (ven-sudhai-maadam), moonlit stucco roofs (nilaa-mutram), and sculpted gateway reliefs.",
        "summary_ta": "பட்டினப்பாலை, நெடுநல்வாடை, மதுரைக்காஞ்சி, பெரும்பாணாற்றுப்படை மற்றும் புறநானூறு ஆகிய சங்க நூல்களில் கிளிஞ்சல் சுண்ணாம்பால் மெழுகப்பட்ட வெள்ளி போன்ற வெண்சுதை மாடங்கள் மற்றும் நிலா முற்றங்கள் பற்றிய இலக்கியச் சான்றுகள்.",
        "sources": [
            "Pattinappalai",
            "Nedunalvadai",
            "Maduraikanchi",
            "Perumpanarruppadai",
            "Purananuru"
        ],
        "content": "# Sangam Literature on Ven-Sudhai White Lime-Plastered Mansions & Stucco Palaces\n\nAcross the Sangam corpus, urban architecture in Kaveripoompattinam, Madurai, Uraiyur, and Kanchipuram is defined by the gleaming visual signature of **ven-sudhai** (*வெண் சுதை*)—burnished white seashell-lime stucco applied over kiln-fired brickwork:\n\n**Poetic & Architectural Attestations (Cited by Title):**\n- **Pattinappalai & Perumpanarruppadai**: Poems describe tall, multi-tiered merchant mansions (*nedun-ilai maadam*) along coastal and riverine highways whose walls are plastered with calcined marine shell lime (*vellai-chunnambu*) polished so smooth that they gleam like freshly washed silver plates (*வெள்ளி அன்ன விளங்கும் சுதை*) and reflect the high-noon sun.\n- **Nedunalvadai**: Details the royal palace inner apartments where master masons (*நூலறி புலவர்*) finish brick walls with white *sudhai* plaster mixed with fragrant binders so smoothly that neither dust nor insects can cling to the mirror-like surface.\n- **Maduraikanchi & Purananuru**: Celebrate lofty turret walls, sculpted *sudhai* friezes of protective deities over fortress gates, and open upper terraces (*nilaa-mutram*) waterproofed with compacted lime concrete."
    },
    {
        "slug": "concept-calcium-carbonate-calcination-thermodynamics-exothermic-slaking-and-recarbonation",
        "category": "concept",
        "file": "concept-calcium-carbonate-calcination-thermodynamics-exothermic-slaking-and-recarbonation.md",
        "name_en": "Thermodynamics of Seashell & Kankar Calcination, Exothermic Slaking & Calcite Recarbonation",
        "name_ta": "கிளிஞ்சல் மற்றும் ஓடைக்கல் சுண்ணாம்பு நீற்றுதல் வெப்ப இயக்கவியலும் வளிமண்டலக் கார்பனேற்ற வேதியியலும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Inorganic physical chemistry of the three-phase Tamil lime cycle: endothermic calcination of biogenic aragonite shells (kilinjal) vs siliceous pedogenic calcrete (odai-kal / kankar) at 900–1000°C to CaO, exothermic slaking (hydration releasing 65 kJ/mol) into sub-micron portlandite putty, and atmospheric CO2 recarbonation.",
        "summary_ta": "கிளிஞ்சல் மற்றும் ஓடைக்கல் சுண்ணாம்புக் கற்களை 900–1000°C வெப்பத்தில் சுட்டுச் சுட்ட சுண்ணாம்பாக்குதல் (CaO), நீர் ஊற்றி வெப்ப உமிழ்வுடன் நீற்றுதல் (Ca(OH)2) மற்றும் காற்றிலுள்ள கார்பன்-டை-ஆக்சைடுடன் இணைந்து மீண்டும் கடினக் கல்லாகும் வேதியியல் சுழற்சி.",
        "sources": [
            "Chemistry and Technology of Ancient Indian Lime Mortars",
            "Mineralogy of Biogenic Aragonite vs Pedogenic Kankar Limes",
            "Archaeometric Studies of Chola & Pallava Temple Plasters"
        ],
        "content": "# Thermodynamics of Calcination, Exothermic Slaking & Calcite Recarbonation\n\nTraditional Tamil masons (*Sthapathis*) distinguish strictly between two geological sources of calcium carbonate ($\\text{CaCO}_3$), exploiting the **closed-loop lime cycle** to turn loose shells and nodules into monolithic artificial limestone:\n\n**1. Endothermic Calcination ($\\sim 900\\text{--}1000^\\circ\\text{C}$):**\n$$\\text{CaCO}_3\\text{ (s)} \\xrightarrow{\\Delta H^\\circ = +178\\text{ kJ/mol}} \\text{CaO (s)} + \\text{CO}_2 \\uparrow$$\n- **Kilinjal / Sangu (Biogenic Marine Shells)**: Composed of $98\\text{--}99.5\\%$ pure orthorhombic **aragonite** interwoven with trace conchiolin protein. Upon firing above $898^\\circ\\text{C}$, it yields snow-white, non-hydraulic **fat lime** ($\\text{CaO}$) ideal for fine *Sudhai* sculpture, frescoes, and edible betel lime.\n- **Odai-Kal / Kankar (Pedogenic Calcrete Nodules)**: Concretionary limestone nodules dug from dryland stream beds contain $15\\text{--}25\\%$ reactive clay silica and alumina. Firing at $950\\text{--}1050^\\circ\\text{C}$ sinters the silica with $\\text{CaO}$ to form **belite ($\\beta\\text{-Ca}_2\\text{SiO}_4$, $\\text{C}_2\\text{S}$)**—creating a natural **hydraulic lime** that sets underwater in tank sluices (*மடை*) and temple foundations.\n\n**2. Exothermic Slaking (*Neertruthal*) & Atmospheric Recarbonation:**\n$$\\text{CaO (s)} + \\text{H}_2\\text{O (l)} \\longrightarrow \\text{Ca(OH)}_2\\text{ (s)} \\quad (\\Delta H^\\circ = -65.2\\text{ kJ/mol})$$\n- The violent steam expansion shatters calcined lumps into high-surface-area hexagonal **portlandite** nano-platelets. Once troweled onto a wall, dissolved pore-water $\\text{Ca(OH)}_2$ absorbs atmospheric $\\text{CO}_2$ to precipitate interlocking **calcite ($\\text{CaCO}_3$)** crystals."
    },
    {
        "slug": "concept-kadukkai-tannin-karuppatti-sucrose-and-vilvam-biopolymer-lime-mortar-chemistry",
        "category": "concept",
        "file": "concept-kadukkai-tannin-karuppatti-sucrose-and-vilvam-biopolymer-lime-mortar-chemistry.md",
        "name_en": "Kadukkai Gall-Nut Tannin, Karuppatti Sucrate & Ovalbumin Biopolymer Lime-Mortar Chemistry",
        "name_ta": "கடுக்காய் டானின், கருப்பட்டி சுக்ரேட், வில்வப் பிசின் மற்றும் முட்டை வெண்கரு கலந்த சுண்ணாம்புச் சாந்து வேதியியல்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Organo-mineral nanocomposite science of Tamil herbal lime mortars (karai-chunnambu and Chettinad palingu-chunnambu): how fermented Terminalia chebula (kadukkai) tannins, palm jaggery (karuppatti) calcium sucrates, Aegle marmelos (vilvam) mucilage, and egg albumen plasticize lime putty, prevent shrinkage cracking, and nucleate vaterite/calcite.",
        "summary_ta": "கடுக்காய் ஊறல் நீர், பனை வெல்லம் (கருப்பட்டி), வில்வப் பிசின் மற்றும் முட்டை வெண்கரு ஆகிய உயிரிப் பலபடிகள் சுண்ணாம்புச் சாந்துடன் வினைபுரிந்து விரிசல் இல்லாத, நீர் புகாத வஜ்ரலேபக் காரையாக மாற்றும் வேதியியல்.",
        "sources": [
            "Biomimetic Role of Fermented Plant Extracts in Ancient Indian Lime Mortars (CSIR / IIT Madras Studies)",
            "Mayamata & Manasara Chapters on Sudhai and Vajralepa",
            "Chettinad Egg-Shell Plaster Craft Documentation"
        ],
        "content": "# Kadukkai Tannin, Karuppatti Sucrate & Ovalbumin Lime-Mortar Chemistry\n\nModern materials characterization (XRD, FTIR, and SEM) of 1,000-year-old Chola and Pandya lime plasters reveals why Tamil *Sthapathis* never used plain water to mix mortar, instead fermenting a complex herbal broth (**kadukkai-karuppatti oorani**):\n\n**1. Calcium Sucrate Solubilization (*Karuppatti* / Palm Jaggery):**\n- Sucrose in unrefined palmyra jaggery reacts with $\\text{Ca(OH)}_2$ to form highly soluble **calcium mono- and di-sucrates**. This increases the concentration of dissolved $\\text{Ca}^{2+}$ ions in the pore fluid by $10\\text{--}15\\times$, accelerating the rate of $\\text{CO}_2$ absorption and carbonation throughout thick masonry joints while acting as a water-reducing superplasticizer.\n\n**2. Polyphenol Chelation & Fermentation CO2 (*Kadukkai* — *Terminalia chebula*):**\n- Crushed *kadukkai* myrobalan pods steeped with jaggery for 14 days undergo yeast/lactic fermentation, generating internal dissolved $\\text{CO}_2$ and organic acids that template metastable **vaterite** and sub-micron **calcite** needles. Hydrolysable gallotannins and chebulagic acid cross-link with $\\text{Ca}^{2+}$ to form hydrophobic calcium-tannate films along capillary pores.\n\n**3. Protein-Mineral Biomineralization (*Palingu-Chunnambu*):**\n- In final mirror-finish coats, **egg-white ovalbumin**, fermented curd **casein**, and *ulunthu* (black gram) globulins unfold at $\\text{pH } 12.4$, binding calcium ions along $\\beta$-sheet protein backbones just like natural mollusk nacre."
    },
    {
        "slug": "concept-sudhai-sirpam-stucco-statuary-mechanics-and-edible-vetrilai-chunnambu-alkalinity",
        "category": "concept",
        "file": "concept-sudhai-sirpam-stucco-statuary-mechanics-and-edible-vetrilai-chunnambu-alkalinity.md",
        "name_en": "Sudhai-Sirpam Gopuram Stucco Structural Mechanics & Edible Vetrilai-Chunnambu Oral Biochemistry",
        "name_ta": "சுதைச் சிற்பக் கட்டுமான இயற்பியலும் வெற்றிலை பாக்குடன் உண்ணும் முத்துச் சுண்ணாம்பின் உயிர்வேதியியலும்",
        "era": "Early Medieval to Modern Era",
        "year_start": 600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Dual architectural and physiological engineering of pure seashell lime: low-dead-weight composite statuary (Sudhai-Sirpam) on towering temple gopurams using chamfered brick cores and graded lime-fiber coats, alongside the oral alkaloid-hydrolysis and calcium-fortification chemistry of edible pearl-shell lime (vetrilai-chunnambu).",
        "summary_ta": "கோயில் கோபுரங்களின் எடையைக் குறைக்கும் சுதைச் சிற்பங்களின் அடுக்குக் கட்டுமான இயற்பியலும், தாம்பூலத்தில் (வெற்றிலை-பாக்கு) சேர்க்கப்படும் கிளிஞ்சல்/முத்துச் சுண்ணாம்பின் காரத்தன்மை மற்றும் கால்சியம் சத்து உயிர்வேதியியலும்.",
        "sources": [
            "Agama & Shilpa Shastra Treatises on Sudhai Iconography",
            "Structural Engineering of South Indian Temple Gopurams",
            "Siddha Pharmacology of Thamboolam (Vetrilai-Paakku-Chunnambu)"
        ],
        "content": "# Sudhai-Sirpam Stucco Mechanics & Edible Vetrilai-Chunnambu Biochemistry\n\nUltra-pure calcined seashell lime (*kilinjal* and *mutthu-chunnambu*) serves two seemingly opposite domains in Tamil civilization—monumental sky-scraping sculpture and daily oral pharmacology:\n\n**1. Structural Mechanics of Gopuram Sudhai-Sirpam:**\n- **Dead-Load Reduction**: A 150-foot brick *Raja-Gopuram* cannot support the concentrated cantilever mass of solid granite statues ($\\rho \\approx 2750\\text{ kg/m}^3$) along its stepped tiers. *Sudhai* stucco figures built over hollow/porous cut-brick cores (*செங்கல் கூடு*) and fired terracotta limb rods (*சலாகை*) have an effective bulk density of $\\rho \\approx 1450\\text{--}1600\\text{ kg/m}^3$, slashing structural dead load by $>40\\%$.\n- **Graded Modulus Hierarchy**: Sculptors apply three progressively finer lime-sand-fiber coats (from coarse 1:3 mortar reinforced with chopped jute/palmyra fiber down to 1:0.5 ground shell-lime skin), matching thermal expansion coefficients across the figure to prevent delamination under tropical sun.\n\n**2. Oral Biochemistry of Edible Thamboolam Lime (*Vetrilai-Chunnambu*):**\n- In the canonical three-part *Thamboolam* (betel leaf + areca nut + slaked shell lime), a dab of culinary *kilinjal/mutthu-chunnambu* ($\\text{pH } 12.0$) converts protonated arecoline salts in *paakku* into free-base arecoline for rapid sublingual absorption, neutralizes cariogenic oral acids after meals, and delivers $40\\text{--}80\\text{ mg}$ of bioavailable ionic calcium per chew."
    },
    {
        "slug": "technology-chunnambu-kalavasal-draft-kiln-charging-and-water-curd-slaking-protocols",
        "category": "technology",
        "file": "technology-chunnambu-kalavasal-draft-kiln-charging-and-water-curd-slaking-protocols.md",
        "name_en": "Chunnambu-Kalavasal Shaft Kiln Charging, Bellows Firing & Curd-Coconut Slaking Technology",
        "name_ta": "சுண்ணாம்புக் காளவாசல் (சூளை) அடுக்கு எரிப்பு, துருத்தி காற்றுச் செலுத்தல் மற்றும் தயிர்-இளநீர் நீற்றுதல் நுட்பம்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Pyrotechnical engineering of the traditional Tamil lime kiln (chunnambu-kalavasal / soozhai): packing alternating beds of washed estuarine clam shells (kilinjal) and palmyra/casuarina charcoal in a refractory clay shaft, firing at 950°C with basal draft tunnels, and slaking quicklime in water, buttermilk, or tender coconut water.",
        "summary_ta": "சுண்ணாம்புக் காளவாசலில் கழுவிய கிளிஞ்சல்களையும் பனை-சவுக்குக் கரியையும் மாறி மாறி அடுக்கி, துருத்தி வழியே காற்றுச் செலுத்தி 950°C வெப்பத்தில் சுட்டு, நன்னீர், மோர் அல்லது இளநீர் ஊற்றி நீற்றும் தொழில்நுட்பம்.",
        "sources": [
            "Traditional Lime Kilns of Coastal Tamil Nadu",
            "Tiruvarur & Thanjavur District Gazetteers (Mineral & Shell Industries)",
            "Indigenous Pyrotechnology of South India"
        ],
        "content": "# Chunnambu-Kalavasal Kiln Charging & Curd-Coconut Slaking Technology\n\nArtisans along the coastal lagoons of Muthupet, Marakkanam, and Pulicat operate specialized vertical shaft kilns (**chunnambu-kalavasal** or **soozhai**) engineered to calcine dense bivalve shells without ash contamination:\n\n**1. Shell Washing & Stratified Kiln Charging:**\n- Dredged estuarine shells (*kilinjal*) are washed in freshwater troughs and sun-dried for a week to leach marine sodium chloride ($\\text{NaCl}$), which would otherwise cause hygroscopic salt efflorescence (*உப்புப் பூத்தல்*) on plastered walls.\n- Inside a truncated conical brick-and-refractory-clay shaft ($2.5\\text{ m}$ diameter, $3\\text{ m}$ height) fitted with a basal iron/brick grate and radial draft tunnels (*காற்றுத் துளை*), kiln-masters lay a kindling bed of dried cow-dung cakes (*வரட்டி*) and palmyra petiole splits (*பனை மட்டை*), followed by alternating $15\\text{ cm}$ layers of wood charcoal and washed shells up to the throat.\n\n**2. Forced-Draft Calcination & Multi-Liquid Slaking (*Neertruthal*):**\n- Leather or rotary blowers (*thuruthi*) drive air through the bottom tunnels until a bright cherry-orange glow ($950\\text{--}1000^\\circ\\text{C}$) rises to the top layer over 18–24 hours.\n- **Architectural Slaking**: Red-hot calcined shells are raked into masonry pits and drenched with river water; the boiling slurry is sieved through brass mesh into aging vats.\n- **Culinary & Icon Grade Slaking**: For *vetrilai-chunnambu* and sanctum *Sudhai* icons, red-hot pearl and cockle shells are quenched in earthen pots using **buttermilk (*மோர்*)** or **tender coconut water (*இளநீர்*)**, yielding an ultra-unctuous, non-caustic calcium lactate-hydroxide paste."
    },
    {
        "slug": "technology-chunnambu-chekku-circular-stone-edge-runner-grinding-and-palingu-burnishing",
        "category": "technology",
        "file": "technology-chunnambu-chekku-circular-stone-edge-runner-grinding-and-palingu-burnishing.md",
        "name_en": "Chunnambu-Chekku Annular Stone Mortar Grinding, Five-Coat Troweling & Palingu Agate Burnishing",
        "name_ta": "சுண்ணாம்புச் செக்கு (கால்வாய்) அரைப்பு, ஐந்து அடுக்குச் சாந்து பூச்சு மற்றும் பளிங்குக் கல் மெருகேற்றும் நுட்பம்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Mechanical milling and multi-stage plastering craft of Tamil masonry: crushing slaked lime, graded quartz sand, and fermented kadukkai-karuppatti broth under a bullock-drawn monolithic granite wheel in a circular stone channel (chunnambu-chekku / kaal-vai), wooden-paddle beating, and quartz-pebble burnishing.",
        "summary_ta": "வட்ட வடிவக் கால்வாய்ச் சுண்ணாம்புச் செக்கில் மாடு கட்டி உருளையால் சுண்ணாம்பு, ஆற்று மணல், கடுக்காய்-கருப்பட்டி நீரை நசுக்கி அரைத்து, ஐந்து அடுக்காகச் சுவரில் பூசிப் பளிங்குக் கல்லால் தேய்த்துக் கண்ணாடி போல் மெருகேற்றும் தொழில்நுட்பம்.",
        "sources": [
            "Chettinad Architecture and Traditional Plastering Manual",
            "Public Works Department Madras Presidency Notes on Indian Mortar Mills (Chunam Chakki)",
            "Conservation Manuals of Tamil Nadu Hindu Religious & Charitable Endowments"
        ],
        "content": "# Chunnambu-Chekku Edge-Runner Grinding & Palingu Agate Burnishing\n\nUnlike simple hoe-mixed cement mortar, the legendary durability of Tamil temple and mansion lime work depends on high-pressure wet attrition milling inside the **chunnambu-chekku** (also called **kaal-vai**):\n\n**1. Bullock-Drawn Annular Edge-Runner Milling (*Chunnambu-Chekku*):**\n- A circular trench ($6\\text{--}8\\text{ m}$ diameter, $45\\text{ cm}$ wide, $40\\text{ cm}$ deep) lined with dressed granite slabs is constructed at the building site. A massive cylindrical granite wheel ($1.2\\text{ m}$ diameter, $800\\text{--}1200\\text{ kg}$) pierced by a radial wooden pole tethered to a central pivot post is pulled around the trough by a pair of bullocks.\n- Slaked shell/kankar lime and washed angular river sand (in $1:2$ or $1:1.5$ ratio) are ground for 6 to 8 hours while fermented *kadukkai*, *karuppatti*, and *vilvam* decoction is ladled in. The crushing shear of the $1\\text{-ton}$ stone wheel fractures sand grains to expose fresh reactive silica surfaces and disperses $\\text{Ca(OH)}_2$ into a cohesive, marshmallow-like paste that does not segregate.\n\n**2. Five-Coat Plastering & Palingu Stone Burnishing:**\n- Masons apply a coarse base coat (*அடிச்சாந்து*), beat it for hours with wooden bats (*தட்டுப் பலகை*) to expel air pockets and consolidate the matrix, follow with medium and fine marble-powder/shell-lime coats, brush on an egg-white/curd glaze, and rub diagonally with smooth jasper or quartz pebbles (**palingu-kal**) until the wall reflects light like polished marble."
    },
    {
        "slug": "artifact-chunnambu-chekku-granite-wheels-palingu-burnishing-stones-and-sudhai-trowels",
        "category": "artifact",
        "file": "artifact-chunnambu-chekku-granite-wheels-palingu-burnishing-stones-and-sudhai-trowels.md",
        "name_en": "Chunnambu-Chekku Granite Edge-Runner Wheels, Wooden Compaction Bats & Palingu Burnishing Stones",
        "name_ta": "சுண்ணாம்புச் செக்குக் கல் உருளைகள், தட்டுப் பலகைகள், சுதைக் கரண்டிகள் மற்றும் பளிங்கு மெருகேற்றும் கற்கள்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Archaeological and artisanal toolkit of Tamil lime masonry and Sudhai sculpting: monolithic perforated granite mortar-mill wheels (chekku-kal) preserved beside historic temples, hardwood impact-compaction paddles (thattu-palagai), leaf-shaped bronze/iron modeling spatulas, and palm-sized agate/quartz burnishing stones.",
        "summary_ta": "பண்டைய கோயில்களின் அருகே காணப்படும் ஒற்றைக் கல் சுண்ணாம்புச் செக்கு உருளைகள், காரையை இறுக்கும் மரத் தட்டுப் பலகைகள், சுதைச் சிற்பக் கரண்டிகள் மற்றும் சுவரைப் பளபளப்பாக்கும் பளிங்குக் கற்கள்.",
        "sources": [
            "Archaeological Remains of Ancient Mortar Mills in Tamil Nadu Temples",
            "Traditional Tools of the South Indian Sthapathi",
            "Chettinad Heritage Building Implements Catalog"
        ],
        "content": "# Chunnambu-Chekku Granite Wheels, Compaction Bats & Burnishing Stones\n\nAround the outer *prakaram* walls of nearly every major Chola, Pandya, and Nayak temple—and in the courtyards of historic Chettinad and Thanjavur mansions—survive the lithic and hand implements of the lime-mason's craft:\n\n**Artifact Typology:**\n1. **Chunnambu-Chekku-Kal (Monolithic Granite Mill Wheels)**: Thick discoidal charnockite or granite rollers ($90\\text{--}130\\text{ cm}$ diameter, $25\\text{--}35\\text{ cm}$ tread width) with a square or circular central axle eye (*அச்சுத் துளை*). Their outer rims are worn glass-smooth by centuries of rolling through quartz-sand and lime slurry inside annular stone troughs.\n2. **Thattu-Palagai & Kottan (Compaction Paddles & Mallets)**: Flat-faced paddles carved from dense seasoned *karuvelam* or *iluppai* wood ($40\\text{ cm}$ long with an offset handle). Used in rhythmic four-person percussion ensembles to beat freshly laid roof terrace concrete (*தளவரிசை*) and wall plasters for 3–5 days, eliminating capillary shrinkage cracks.\n3. **Sudhai-Karandi & குச்சி (Stucco Modeling Spatulas)**: Double-ended iron, bronze, and bamboo-splint modeling tools with willow-leaf and spoon tips for sculpting fingernails, jewelry, and eyelids on wet *gopuram* figures.\n4. **Palingu-Kal / Vazhavazhappu-Kal (Burnishing Pebbles)**: Egg-shaped, ultra-dense river-rolled chalcedony, agate, or milky quartz stones held in the palm to compress the final egg-shell lime skin."
    },
    {
        "slug": "artifact-kilinjal-clam-shells-kankar-nodules-and-brass-vetrilai-chunnambu-dappa-caskets",
        "category": "artifact",
        "file": "artifact-kilinjal-clam-shells-kankar-nodules-and-brass-vetrilai-chunnambu-dappa-caskets.md",
        "name_en": "Kilinjal Estuarine Clam Shells, Kankar Nodules & Brass Vetrilai Chunnambu-Dappa Lime Caskets",
        "name_ta": "கழிமுகக் கிளிஞ்சல்கள், ஓடைக்கல் சுண்ணாம்புக் கட்டிகள் மற்றும் பித்தளை வெற்றிலைச் சுண்ணாம்புக் கூடுகள் (டப்பா)",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Raw mineral/biogenic feedstocks and domestic consumption artifacts of Tamil lime culture: sub-fossil Meretrix and Anadara estuarine shells (kilinjal), pearl-oyster valves (mutthu-chippi), botryoidal kankar calcrete nodules, and intricately cast brass/silver pocket lime containers (chunnambu-koodu / dappa) with chained spatulas.",
        "summary_ta": "சுண்ணாம்பு மூலப்பொருட்களான கழிமுகக் கிளிஞ்சல்கள், முத்துச் சிப்பிகள், ஓடைக்கற்கள் மற்றும் வெற்றிலை மடிப்புடன் பயன்படுத்தப்படும் சங்கிலி இணைத்த பித்தளை, வெள்ளிச் சுண்ணாம்புக் கூடுகள்.",
        "sources": [
            "Marine Molluscan Resources of Tamil Nadu Lagoons (CMFRI)",
            "Decorative Betel-Nut & Lime Containers of South India",
            "Government Museum Chennai Metalware Collection"
        ],
        "content": "# Kilinjal Shells, Kankar Nodules & Brass Chunnambu-Dappa Caskets\n\nThe material record of Tamil lime spans raw estuarine shell middens to miniature personal metalwork carried in every elder's betel pouch (*vetrilai-potti*):\n\n**1. Biogenic & Pedogenic Feedstocks:**\n- **Kilinjal & Sangu (Estuarine Bivalves & Gastropods)**: Ribbed blood-cockle valves (*Anadara granosa*), smooth backwater clam shells (*Meretrix casta* and *Villorita cyprinoides*), and horn snails (*Telescopium*) harvested from sub-fossil lagoon beds ($1\\text{--}3\\text{ m}$ thick) accumulated over millennia along coastal backwaters.\n- **Mutthu-Chippi (Pearl Oyster Valves)**: Nacreous *Pinctada fucata* shells from the Gulf of Mannar calcined specifically for luxury medicinal and culinary *mutthu-chunnambu*.\n- **Odai-Kal / Kankar Nodules**: Irregular, knobby gray-white calcium carbonate concretions ($2\\text{--}8\\text{ cm}$ across) precipitated in semi-arid black cotton and red soils.\n\n**2. Chunnambu-Koodu / Chunnambu-Dappa (Pocket Lime Caskets):**\n- Cylindrical, octagonal, or mango-shaped miniature canisters cast in brass, bell-metal, or silver with a tight-fitting telescoping lid to prevent atmospheric $\\text{CO}_2$ from drying out the moist edible lime paste. A slender brass chain links the lid to a leaf-tipped applicator pin (*சுண்ணாம்புக் குச்சி*) used to lift a single rice-grain-sized dot of lime onto the betel leaf."
    },
    {
        "slug": "institution-chunnambukkarar-kiln-guilds-lagoon-shell-quarry-leases-and-stucco-sthapathis",
        "category": "institution",
        "file": "institution-chunnambukkarar-kiln-guilds-lagoon-shell-quarry-leases-and-stucco-sthapathis.md",
        "name_en": "Chunnambukkarar Kiln-Master Guilds, Lagoon Shell Quarry Leases & Sudhai-Sthapathi Lineages",
        "name_ta": "சுண்ணாம்புக்காரர் சூளைக் குழுக்கள், கிளிஞ்சல் பாட்டம் குத்தகை முறை மற்றும் சுதைச் சிற்பி (ஸ்தபதி) மரபுகள்",
        "era": "Medieval to Modern Era",
        "year_start": 700,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Socio-economic and epigraphic institutions governing lime production and stucco architecture in Tamil Nadu: hereditary Chunnambukkarar kiln guilds holding lagoon shell-dredging leases (kilinjal-pattam), medieval temple inscriptions recording chunnambu-vari taxes and whitewashing grants, and Sudhai-Sthapathi sculptor lineages.",
        "summary_ta": "கழிமுகங்களில் கிளிஞ்சல் எடுக்கும் பாட்டம் குத்தகை உரிமை பெற்ற சுண்ணாம்புக்காரர் கைவினைக் குழுக்கள், கல்வெட்டுகளில் சுண்ணாம்பு வரி மற்றும் திருவெள்ளை சாத்துதல் கொடைகள், மற்றும் கோபுரச் சுதைச் சிற்பி மரபுகள்.",
        "sources": [
            "South Indian Inscriptions (Temple Renovation & Lime Grants)",
            "Thanjavur & Tiruvarur District Manuals (Fisheries and Shell Leases)",
            "Guild Organization of Traditional Sthapathis in Tamil Nadu"
        ],
        "content": "# Chunnambukkarar Kiln Guilds, Shell Quarry Leases & Sudhai-Sthapathi Lineages\n\nMonumental temple building and urban housing in pre-modern Tamil Nadu depended on a regulated supply chain linking coastal shell-dredgers, kiln operators, and temple architectural guilds:\n\n**1. Lagoon Shell Leases (*Kilinjal-Pattam*) & Chunnambukkarar Guilds:**\n- Hereditary **Chunnambukkarar** (*Chunnar*) families organized both the mining of inland *kankar* pits and the boat-dredging of coastal shell beds. Under Chola, Nayak, and Maratha revenue administration, lagoon shell-mining rights (**kilinjal-pattam**) were auctioned by the state or endowed directly to great temples to guarantee an uninterrupted supply of high-grade lime for structural maintenance.\n\n**2. Epigraphic Whitewashing & Plastering Endowments (*Thiruvellai-Chathuthal*):**\n- Stone inscriptions across Tamil Nadu record perpetual endowments (*kattalai*) funding periodic lime whitewashing (**திருவெள்ளை சாத்துதல்**) of temple enclosure walls and granaries before major *Brahmotsavam* festivals, alongside fiscal exemptions on *chunnambu-chekku* mills working on sacred constructions.\n\n**3. Sudhai-Sthapathi Sculptor Lineages:**\n- Distinct from stone-carving *Kal-Sthapathis*, specialized **Sudhai-Sthapathi** families master the rapid, additive art of modeling wet herbal-lime mortars before carbonation sets in—executing the mandatory 12-year **Samprokshanam / Kumbhabhishekam** restoration of thousands of *gopuram* deities."
    },
    {
        "slug": "place-muthupet-ancient-lagoon-seashell-calcination-and-chunnambu-kiln-haven",
        "category": "place",
        "file": "place-muthupet-ancient-lagoon-seashell-calcination-and-chunnambu-kiln-haven.md",
        "name_en": "Muthupet: Ancient Kaveri Delta Lagoon Seashell Dredging & Chunnambu Kiln Haven",
        "name_ta": "முத்துப்பேட்டை - காவிரி கழிமுக அலையாத்திக் காட்டுக் கிளிஞ்சல் அகழ்வு மற்றும் சுண்ணாம்புக் காளவாசல் தளம்",
        "era": "Early Medieval to Modern Era",
        "year_start": 700,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Historic coastal lagoon town at the southern tail of the Kaveri delta in Tiruvarur district (lat 10.4000, lng 79.5000, thinai: neithal), where six distributary rivers meet the Palk Strait mangroves, creating vast sub-fossil clam and cockle shell beds (kilinjal) that have fueled traditional chunnambu-kalavasal lime kilns for over a millennium.",
        "summary_ta": "திருவாரூர் மாவட்டத்தில் காவிரியின் கிளையாறுகள் பாக் நீரிணையில் கலக்கும் முத்துப்பேட்டை (lat 10.4000, lng 79.5000, நெய்தல் திணை): அலையாத்திக் கழிமுகக் கிளிஞ்சல் படிவுகளும், சோழர் காலம் முதல் கோயில்களுக்கும் தாம்பூலத்திற்கும் வெண் சுண்ணாம்பு வழங்கும் சூளைகளும் நிறைந்த வரலாற்றுத் தளம்.",
        "sources": [
            "Tanjore / Tiruvarur District Gazetteer (Muthupet Lagoon & Shell Lime Industry)",
            "Quaternary Geology and Sub-Fossil Shell Beds of the Cauvery Delta",
            "Traditional Lime Craft of Coastal Chola Nadu"
        ],
        "content": "# Muthupet: Ancient Kaveri Delta Lagoon Seashell & Chunnambu Kiln Haven\n\nSituated at `lat 10.4000, lng 79.5000` along the *Neithal–Marutham* estuarine margin of Tiruvarur district (where the Koraiyar, Paminiyar, Kilaithangiyar, Marakkakoraiyar, and Valavanar distributaries of the Kaveri empty into a vast shallow mangrove lagoon bordering the Palk Strait), **Muthupet** has served for over a thousand years as the premier biogenic lime foundry of the Chola heartland:\n\n**Geological & Pyrotechnical Significance:**\n- **Holocene Sub-Fossil Shell Beds (*Kilinjal-Padugai*)**: Because the granite-poor lower Kaveri delta lacks inland limestone outcrops, builders of the great Chola and Nayak brick-and-stucco monuments turned to Muthupet's brackish lagoon floor, where nutrient-rich river silt supports immense beds of *Meretrix* clams, *Anadara* cockles, and oysters compacted into meter-thick sub-fossil shell strata.\n- **Lagoon Dredging & Kiln Batteries**: Local *Chunnambukkarar* crews wade into the shallow mudflats with long-handled iron-toothed basket rakes (*கிளிஞ்சல் வலைக்கூடை*) to scoop shells into flat-bottomed boats, wash them in the freshwater Koraiyar, and fire them in rows of cylindrical *chunnambu-kalavasal* kilns lining the lagoon shore—producing both architectural *sudhai* lime and prized culinary *Muthupet Vetrilai-Chunnambu*."
    }
]

EDGES = [
    [
        "text-sangam-literature-on-ven-sudhai-white-lime-mansions-and-stucco-palaces",
        "describes",
        "concept-sudhai-sirpam-stucco-statuary-mechanics-and-edible-vetrilai-chunnambu-alkalinity",
        "material_culture",
        "Sangam to Modern Era",
        "Pattinappalai, Nedunalvadai, and Maduraikanchi celebrate gleaming silver-white ven-sudhai lime plasters and sculpted stucco gateways.",
        "Pattinappalai & Nedunalvadai"
    ],
    [
        "concept-calcium-carbonate-calcination-thermodynamics-exothermic-slaking-and-recarbonation",
        "governs",
        "technology-chunnambu-kalavasal-draft-kiln-charging-and-water-curd-slaking-protocols",
        "material_culture",
        "Sangam to Modern Era",
        "Endothermic aragonite/calcite decomposition at 950°C and exothermic hydration kinetics direct kiln firing and water/curd slaking protocols.",
        "Ancient Indian Lime Chemistry"
    ],
    [
        "concept-calcium-carbonate-calcination-thermodynamics-exothermic-slaking-and-recarbonation",
        "characterizes",
        "artifact-kilinjal-clam-shells-kankar-nodules-and-brass-vetrilai-chunnambu-dappa-caskets",
        "material_culture",
        "Sangam to Modern Era",
        "Pure aragonite estuarine kilinjal shells yield fat white lime whereas siliceous kankar nodules produce hydraulic belite-bearing lime.",
        "Mineralogy Studies"
    ],
    [
        "concept-kadukkai-tannin-karuppatti-sucrose-and-vilvam-biopolymer-lime-mortar-chemistry",
        "underpins",
        "technology-chunnambu-chekku-circular-stone-edge-runner-grinding-and-palingu-burnishing",
        "material_culture",
        "Sangam to Modern Era",
        "Calcium sucrate solubilization from palm jaggery and gallotannin chelation from fermented kadukkai occur during wet grinding in the chunnambu-chekku.",
        "IIT Madras Lime Mortar Studies"
    ],
    [
        "concept-sudhai-sirpam-stucco-statuary-mechanics-and-edible-vetrilai-chunnambu-alkalinity",
        "explains",
        "artifact-kilinjal-clam-shells-kankar-nodules-and-brass-vetrilai-chunnambu-dappa-caskets",
        "material_culture",
        "Sangam to Modern Era",
        "Edible pearl-shell slaked lime carried in brass chunnambu-dappa caskets hydrolyzes areca alkaloids and supplies dietary calcium in thamboolam.",
        "Siddha Pharmacology"
    ],
    [
        "technology-chunnambu-kalavasal-draft-kiln-charging-and-water-curd-slaking-protocols",
        "processes",
        "artifact-kilinjal-clam-shells-kankar-nodules-and-brass-vetrilai-chunnambu-dappa-caskets",
        "material_culture",
        "Sangam to Modern Era",
        "Stratified charcoal-and-shell firing in the chunnambu-kalavasal kiln converts washed estuarine kilinjal shells into quicklime and slaked putty.",
        "Tiruvarur District Gazetteer"
    ],
    [
        "technology-chunnambu-chekku-circular-stone-edge-runner-grinding-and-palingu-burnishing",
        "employs",
        "artifact-chunnambu-chekku-granite-wheels-palingu-burnishing-stones-and-sudhai-trowels",
        "material_culture",
        "Sangam to Modern Era",
        "Mortar attrition milling, wall compaction, and mirror polishing rely on monolithic granite chekku wheels, wooden bats, and palingu quartz pebbles.",
        "Chettinad Plastering Manual"
    ],
    [
        "institution-chunnambukkarar-kiln-guilds-lagoon-shell-quarry-leases-and-stucco-sthapathis",
        "operates",
        "technology-chunnambu-kalavasal-draft-kiln-charging-and-water-curd-slaking-protocols",
        "material_culture",
        "Medieval to Modern Era",
        "Hereditary Chunnambukkarar kiln guilds manage lagoon shell dredging leases and operate coastal chunnambu-kalavasal shaft kilns.",
        "South Indian Inscriptions"
    ],
    [
        "institution-chunnambukkarar-kiln-guilds-lagoon-shell-quarry-leases-and-stucco-sthapathis",
        "flourishes_in",
        "place-muthupet-ancient-lagoon-seashell-calcination-and-chunnambu-kiln-haven",
        "material_culture",
        "Early Medieval to Modern Era",
        "Chunnambukkarar shell-dredging and kiln-burning guilds cluster around the Muthupet mangrove lagoon to supply the Kaveri delta.",
        "Tanjore District Gazetteer"
    ],
    [
        "text-sangam-literature-on-ven-sudhai-white-lime-mansions-and-stucco-palaces",
        "celebrates",
        "place-muthupet-ancient-lagoon-seashell-calcination-and-chunnambu-kiln-haven",
        "material_culture",
        "Sangam to Modern Era",
        "Coastal Neithal seashell lime production along the Kaveri delta lagoons sustained the gleaming ven-sudhai architecture praised in classical literature.",
        "Pattinappalai"
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
