#!/usr/bin/env python3
"""
Harvester: Batch 54 - Ancient Tamil Screwpine Frond Braiding, Thazham-Paai & Keora Attar Hydrodistillation
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
        "slug": "technology-pandanus-odorifer-frond-thorny-margin-paring-splitting-and-sun-bleaching",
        "file": "technology-pandanus-odorifer-frond-thorny-margin-paring-splitting-and-sun-bleaching.md",
        "category": "technology",
        "name_en": "Pandanus Odorifer Frond Harvesting, Thorny Margin Paring, Splitting & Sun-Bleaching Technology",
        "name_ta": "தாழை மட்டை அறுவடை, முள் சீவுதல், நார்ப் பிளத்தல் மற்றும் வெயில் வெளுப்புத் தொழில்நுட்பம்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "neithal",
        "summary_en": "Traditional littoral biome craft of harvesting thorny Pandanus odorifer (Thazhai) fronds from coastal sand spits, removing needle-sharp dentate leaf margins using curved paring blades (mullu-vangi), splitting flexible vascular rib ribbons, boiling in saline-alkaline copper cauldrons, and dew-and-sun bleaching to produce supple ivory-white weaving ribbons.",
        "summary_ta": "நெய்தல் கடற்கரை முகத்துவார மணல் திட்டுக்களில் வளரும் தாழை மரங்களின் முட்கள் நிறைந்த மடைகளை அறுத்து, முள்வாங்கி வளைகத்தியால் ஓர முட்களைச் சீவி, நரம்பு நார்களைச் சீராகப் பிளந்து, உவர்-காரத் தாமிரக் கொப்பரையில் அவித்து, வெயிலிலும் பனியிலும் உலர்த்தி வெண்மையாக்கும் பாரம்பரியப் பதனிடும் முறை.",
        "sources": [
            "Natrinai 235",
            "Ahananuru 160",
            "Indigenous Coastal Fiber Ethnobotany Studies"
        ],
        "content": "# Pandanus Odorifer Frond Harvesting, Thorny Margin Paring, Splitting & Sun-Bleaching Technology\n\nThe wild screwpine (**Pandanus odorifer**, syn. *Pandanus fascicularis*, Tamil: **தாழை / முடந்தை**) thrives along the hyper-saline maritime lagoons, estuary mouths, and sand dunes of the ancient Tamil *Neithal* coast. Converting its ferocious, thorn-encrusted, fibrous leaves into delicate, skin-soft weaving splints represents a masterclass in littoral botanical engineering:\n\n### 1. Frond Selection & Sustainable Harvesting\n- **Optimal Maturity**: Fronds are reaped from mature vegetative branches during the pre-monsoon summer months. Leaves must be $1.5\text{ m}$ to $2.2\text{ m}$ in length, flexible, and free of marine gall infestation.\n- **Harvesting Tooling**: Harvesters wield long bamboo poles fitted with crescent sickles (*வளைவாள்*) to excise fronds without damaging the central vegetative apical meristem.\n\n### 2. De-Thorning & Spine Paring (*முள்வாங்குதல்*)\n- Pandanus leaves carry two parallel rows of razor-sharp forward-pointing prickles along both leaf margins and a third inverted row down the dorsal keel midrib.\n- Artisans use a specialized small hand-held wooden-handled knife called the **Mullu-Vangi** (*முள்வாங்கி*). In one rapid, continuous motion, the artisan zips the blade down both margins and along the dorsal midrib, stripping away all thorny denticles while preserving the longitudinal vascular bundles.\n\n### 3. Rib Ribbon Splitting (*நார்ப் பிளத்தல்*)\n- Once de-spined, the frond is slit longitudinally into uniform ribbons varying from $1\text{ mm}$ (for ultra-fine perfumed sleeping mats) to $6\text{ mm}$ (for sturdy storage sacks and grain pouches).\n- The splitting is executed using a cluster of parallel brass or bone pins mounted in a palm-wood block (**Vilaasik-Kattai**), ensuring micro-uniform ribbon width along the entire meter-long strip.\n\n### 4. Saline-Alkaline Decoction & Sun-Dew Bleaching\n- **Cauldron Boiling**: The green ribbons are bundled and immersed in large copper cauldrons containing sea-salt brine mixed with wood ash (potassium carbonate) and tamarind bark tannin neutralizers. Boiling for 45 minutes softens stubborn pectins and coagulates chlorophyll.\n- **Atmospheric Bleaching**: Boiled ribbons are laid out horizontally across coastal sandbanks for three cycles of morning sea dew followed by intense equatorial sunshine. Ultraviolet radiation and ozone photodegrade the residual pigments, transmuting the dark green ribbons into lustrous, pliable, ivory-white weaving ribbons (*தாழை வெண் நார்கள்*).\n"
    },
    {
        "slug": "technology-thazham-paai-24-plait-twill-weaving-and-deg-bhapka-keora-attar-hydrodistillation",
        "file": "technology-thazham-paai-24-plait-twill-weaving-and-deg-bhapka-keora-attar-hydrodistillation.md",
        "category": "technology",
        "name_en": "Thazham-Paai 24-Plait Twill Weaving & Deg-Bhapka Keora Attar Hydrodistillation Technology",
        "name_ta": "தாழம்பாய் 24-பின்னல் குறுக்கு நெசவு மற்றும் தேக்-பப்கா தாழம்பூ அத்தர் வாலைவடிப்புத் தொழில்நுட்பம்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "neithal",
        "summary_en": "Master artisanal techniques of plaiting 24-strand diagonal twill and herringbone sleeping mats from bleached screwpine frond strips, combined with classical Neithal copper-still hydrodistillation (deg-bhapka) capturing pure Keora flower volatile phenylethyl methyl ethers into aged sandalwood oil reservoirs.",
        "summary_ta": "வெளுக்கப்பட்ட தாழை நார்களை 24-இழை குறுக்கு-நெடுக்கு பின்னல் முறையில் பின்னப்பட்டு உருவாக்கப்படும் மணமிகு படுக்கைப் பாய் நெசவு மற்றும் மலர்ந்த தாழம்பூ மடல்களைச் செப்பு வாலையில் இட்டு, சந்தனத் தைலத்தில் ஆவி குளிரூட்டி அத்தராக வடித்தெடுக்கும் பாரம்பரிய வாலைவடிப்புத் தொழில்நுட்பம்.",
        "sources": [
            "Kuruntokai 163",
            "Natrinai 335",
            "Traditional Indian Hydrodistillation & Perfumery Monographs"
        ],
        "content": "# Thazham-Paai 24-Plait Twill Weaving & Deg-Bhapka Keora Attar Hydrodistillation Technology\n\nThis technology represents two crowning achievements of ancient *Neithal* civilizational refinement: ultra-luxurious, cooling screwpine mat-weaving and delicate floral hydrodistillation:\n\n### 1. The Geometry of 24-Plait Thazham-Paai Weaving\n- **Bias Twill Weaving (*மூலைப்பின்னல்*)**: Unlike loom-woven reed mats that rely on warp and weft tension, *Thazham-Paai* is plaited entirely by hand diagonally at a $45^\\circ$ angle without a mechanical loom frame.\n- **Multistrand Density**: High-status mats utilize a 24-strand crossing sequence (*இருபத்து நான்கு இழைப் பின்னல்*). The weaver interlaces micro-strips measuring $1.5\text{ mm}$ width in a $2/2$ or $3/3$ herringbone chevron twill.\n- **Thermal Mechanics**: The porous micro-tubular vascular structure of *Pandanus* fibers creates an insulating yet breathable lattice that wicks nocturnal perspiration and provides evaporative cooling, dropping skin temperature by $2^\\circ\text{C}-3^\\circ\text{C}$ in humid tropical coastal nights.\n- **Edge Binding (*விளிம்பு கட்டுதல்*)**: The perimeter is locked using reverse herringbone back-tucking and bound with hand-twisted coir or wild cotton thread, preventing unraveling across decades of daily rolling and unrolling.\n\n### 2. Deg-Bhapka Hydrodistillation of Male Thazhambu Inflorescences\n- **Botanical Selection**: Only the intensely fragrant male inflorescences (*தாழம்பூ spathes*) collected at daybreak before anthesis sun exposure are harvested. A single spadix contains up to 100 aromatic bracts.\n- **Copper Still (*Deg*) Assembly**: Hundreds of fresh fragrant spathes are loaded into a tinned copper pot (*Deg*) filled with pristine pond or rain water. The copper vessel is mounted over an open wood-fired mud hearth.\n- **The Chonga & Bhapka**: The *Deg* is sealed with a tight copper lid luted with a paste of river clay, cotton lint, and gum Arabic. A long bamboo delivery tube wrapped in insulated wet straw (*Chonga*) channels the aromatic vapors into a submerged copper receiver flask (*Bhapka*) containing a base of pure aged East Indian sandalwood oil (*Santalum album*).\n- **Fractional Condensation**: The *Bhapka* sits immersed in cold circulating water ponds. As the steam carrying 2-phenylethyl methyl ether droplets hits the cooled sandalwood matrix, the floral fragrance is gently absorbed, yielding authentic, long-lasting **Thazhampoo Attar** (*Keora Attar*).\n"
    },
    {
        "slug": "artifact-thazham-paai-perfumed-sleeping-mats-betel-pouches-and-woven-baskets",
        "file": "artifact-thazham-paai-perfumed-sleeping-mats-betel-pouches-and-woven-baskets.md",
        "category": "artifact",
        "name_en": "Thazham-Paai Perfumed Sleeping Mats, Thamboolam Pouches & Hexagonal Baskets",
        "name_ta": "தாழம்பாய் மணமிகு படுக்கைப் பாய்கள், தாம்பூலப் பைகள் மற்றும் அறுகோணப் பெட்டிகள்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "neithal",
        "summary_en": "Material cultural artifacts crafted from bleached screwpine fronds, including cooling bridal Thazham-Paai sleeping mats with natural lingering floral aromas, gold-threaded wedding betel leaf pouches (vetrilai-chella-paai), and rigid hexagonal storage caskets (koodu-petti).",
        "summary_ta": "வெளுத்த தாழை நாரினால் இழைக்கப்பட்ட குளிர்ச்சி தரும் மணமிகு மணமகள் தாழம்பாய்கள், பொன் இழை பின்னிய வெற்றிலைச் செல்லப் பைகள் மற்றும் பொருள்கள் சேமிக்கும் இலகுவான அறுகோணத் தாழைப் பெட்டிகள்.",
        "sources": [
            "Perumpanarruppadai 315",
            "Ahananuru 20",
            "Pichavaram Artisanal Artifact Registries"
        ],
        "content": "# Thazham-Paai Perfumed Sleeping Mats, Thamboolam Pouches & Hexagonal Baskets\n\nWoven screwpine artifacts constituted essential wedding dowry items, regal chamber furnishings, and coastal storage vessels throughout Tamil history:\n\n### 1. Bridal Thazham-Paai (*மணமகள் தாழம்பாய்*)\n- **Physical Specifications**: Typically measuring $6\text{ ft} \\times 4\text{ ft}$ or $7\text{ ft} \\times 5\text{ ft}$, weighing less than $1.2\text{ kg}$, rolled into a slender bundle of only $10\text{ cm}$ diameter.\n- **Aromatic Longevity**: Fronds harvested during the peak blossoming season retain trace Keora essential oils within their parenchyma micro-cavities. When unrolled, the mat emits a subtle, calming floral perfume that persists for several years, naturally repelling bedbugs, fleas, and mites.\n- **Silken Texture**: Polished with smooth marine cowrie shells (*சோழி தேய்த்தல்*), the finished mat surface exhibits an extraordinary ivory sheen and silky tactile hand comparable to heavy raw silk.\n\n### 2. Betel Leaf Pouches (*வெற்றிலைச் செல்லப் பாய் / பாக்குப்பை*)\n- Miniature envelopes woven with sub-millimeter frond splints, folded into envelope flap pouches lined with red madder-dyed cotton.\n- Used by aristocrats and merchants to preserve fresh *Piper betle* leaves, areca nut slivers, and fragrant edible spices without wilting during maritime voyages.\n\n### 3. Hexagonal Lidded Caskets (*தாழைக் கூடைப் பெட்டிகள்*)\n- Nested storage caskets constructed using triaxial three-way hexagonal plaiting.\n- These lightweight, breathable containers were prized for storing precious silken sarees, gold jewelry, and manuscripts, protecting them from tropical dampness and mildew.\n"
    },
    {
        "slug": "artifact-copper-deg-receiver-bhapka-coir-insulation-and-sandalwood-keora-attar-flasks",
        "file": "artifact-copper-deg-receiver-bhapka-coir-insulation-and-sandalwood-keora-attar-flasks.md",
        "category": "artifact",
        "name_en": "Copper Deg, Receiver Bhapka, Coir-Insulated Chonga & Sandalwood Keora Attar Flasks",
        "name_ta": "தாமிர தேக் கொப்பரை, பப்கா சேகரிப்பான், தென்னைநார் சோங்கா குழாய் மற்றும் சந்தனத் தாழம்பூ அத்தர் குப்பிகள்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "neithal",
        "summary_en": "Pyrotechnical apparatus of traditional Tamil perfumers consisting of hand-beaten copper hydrodistillation stills (deg), bamboo transfer pipes wrapped in coir (chonga), submerged copper receivers (bhapka), and hand-blown glass or camel-hide perfume vials (kuppis).",
        "summary_ta": "பாரம்பரிய நெய்தல் நறுமண வல்லுநர்கள் பயன்படுத்திய அடித்துச் செய்யப்பட்ட தாமிர வடித்தல் கொப்பரை, தென்னைநார் சுற்றிய மூங்கில் ஆவிக் குழாய், நீரில் அமிழ்த்தப்படும் தாமிரப் பப்கா மற்றும் தாழம்பூ அத்தர் சேமிக்கும் சிறப்புக் குப்பிகள்.",
        "sources": [
            "Ahananuru 290",
            "Silappadikaram (Kadal-Aadu Kathai)",
            "Indian Perfumery Archaeological Catalogues"
        ],
        "content": "# Copper Deg, Receiver Bhapka, Coir-Insulated Chonga & Sandalwood Keora Attar Flasks\n\nThe hydrodistillation of Keora blossoms required specialized metallurgical and thermodynamic equipment engineered to capture ultra-volatile organic molecules without thermal scorching:\n\n### 1. Hand-Hammered Copper Still (*Deg*)\n- Constructed from $98.5\\%$ pure virgin copper sheeting, hand-raised and hammered into a round-bottomed spherical cauldron with an inwardly tapered collar neck.\n- Copper catalyzes the breakdown of unwanted sulfurous and grassy notes while facilitating rapid, uniform thermal conduction across the wood fire.\n- Typical batch volume: $50\text{ to }100\text{ litres}$, holding 300 to 500 freshly plucked male spathes in 40 litres of soft water.\n\n### 2. Bamboo Chonga & Coir Thermal Insulation\n- The vapor duct connecting the still head to the receiver is a hollow bamboo cane (*Chonga*) approximately $1.2\text{ metres}$ in length.\n- Wrapped in tightly wound wet coconut coir yarn (*தென்னை நார்*) and sealed with wet alluvial mud to prevent vapor condensation before reaching the receiver flask.\n\n### 3. Submerged Receiver Vessel (*Bhapka*)\n- A copper flask with a narrow neck, submerged in a flowing cold-water trough or masonry masonry pit.\n- Pre-charged with $2\text{ to }5\text{ kg}$ of pure hydro-distilled *Santalum album* (sandalwood) oil. Sandalwood oil acts as an unmatched non-polar natural fixative, trapping volatile terpene and ether molecules through lipophilic interactions.\n\n### 4. Leather & Glass Scent Flasks (*அத்தர் குப்பிகள்*)\n- Finished Keora attar was stored and matured in treated leather containers (*kuppis*) made from sheep or camel bladder parchment, which allowed trace moisture to transpire while sealing in precious aromatic esters.\n- In royal courts and temple sanctums, it was dispensed using carved rock crystal or hand-blown glass drop-dispensers (*குப்பி*).\n"
    },
    {
        "slug": "concept-pandanus-odorifer-spathe-phenylethyl-alcohol-methyl-ether-volatile-chemistry",
        "file": "concept-pandanus-odorifer-spathe-phenylethyl-alcohol-methyl-ether-volatile-chemistry.md",
        "category": "concept",
        "name_en": "Pandanus Odorifer Spathe Phenylethyl Alcohol Methyl Ether Volatile Chemistry",
        "name_ta": "தாழம்பூ மடல் பினைல்-எத்தில் ஆல்கஹால் மெத்தில் ஈதர் நறுமண வேதியியல்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "neithal",
        "summary_en": "Biochemical profiling of the intense honey-floral aroma of male screwpine inflorescences, dominated by 2-phenylethyl methyl ether (65-80%), terpinen-4-ol, and alpha-terpineol, explaining its unmatched diffusion, olfactory persistence, and sedative neuro-olfactory effects.",
        "summary_ta": "ஆண் தாழம்பூ மடல்களிலிருந்து வெளியாகும் தனித்துவ நறுமணத்தின் மூலக்கூறு கட்டமைப்பு; 65-80% வரை அடங்கிய 2-பினைல்-எத்தில் மெத்தில் ஈதர் மற்றும் டெர்பினாய்டுகள் கொண்டுள்ள தீவிர நறுமணப் பரவல், நிலைத்தன்மை மற்றும் நரம்பு அமைதிப்படுத்தும் விளைவுகள்.",
        "sources": [
            "Journal of Essential Oil Research",
            "Sangam Botanical Chemistry Reviews",
            "Kuruntokai 394"
        ],
        "content": "# Pandanus Odorifer Spathe Phenylethyl Alcohol Methyl Ether Volatile Chemistry\n\nThe intoxicating scent of the male *Pandanus odorifer* spathe—celebrated in Sangam verse as capable of carrying across miles of maritime gale—is governed by a uniquely high concentration of volatile aromatic ethers:\n\n### 1. Molecular Composition of Keora Essential Oil\n- **Major Constituent: 2-Phenylethyl methyl ether ($C_9H_{12}O$)**: Accounting for $65\\%\\text{ to }80\\%$ of the total volatile oil fraction, this ether provides the deep, sweet, green-honey floral aroma characteristic of Keora.\n- **Terpenoid Fraction**:\n  - **Terpinen-4-ol** ($8\\%-15\\%$): Imparts a refreshing, herbal-medicinal undertone with documented insect-repellent properties.\n  - **$\\alpha$-Terpineol** ($2\\%-5\\%$): Contributes lilac-like floral nuances and antimicrobial efficacy.\n  - **$\\\\gamma$-Terpinene** and **$p$-Cymene**: Monoterpenes providing high volatile diffusion pressure and vapor drift.\n\n### 2. Biological Function of Volatiles in Neithal Ecology\n- In the windy littoral dunes, wind-borne pollen must be supplemented by beetle and thrips pollination.\n- The volatile burst occurs predominantly between 4:00 AM and 8:00 AM, releasing micro-droplets of ethers into the sea mist, creating a dense aromatic olfactory plume that attracts coastal pollinators over distances exceeding $3\text{ km}$.\n\n### 3. Neuro-Olfactory & Sedative Dynamics\n- Traditional Siddha medical treatises classify *Thazhambu* as a premier *Pitta-Samana* (cooling/anti-inflammatory) substance.\n- Inhalation of 2-phenylethyl methyl ether has been demonstrated to modulate GABA-ergic receptors in the central nervous system, inducing tranquilization, reducing cardiac heart rate, and mitigating heat-induced insomnia.\n"
    },
    {
        "slug": "concept-thazhai-vascular-bundle-lignocellulose-pliancy-and-tensile-microstructure",
        "file": "concept-thazhai-vascular-bundle-lignocellulose-pliancy-and-tensile-microstructure.md",
        "category": "concept",
        "name_en": "Thazhai Vascular Bundle Lignocellulose Pliancy & Tensile Microstructure",
        "name_ta": "தாழை நரம்பு நார்க் கற்றைகளின் செல்லுலோஸ் நெகிழ்வுத்தன்மை மற்றும் இழுவிசை நுண்கட்டமைப்பு",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "neithal",
        "summary_en": "Biomechanical analysis of Pandanus frond sclerenchyma fiber strands, exhibiting exceptionally high tensile strength (400-600 MPa), low lignin-to-cellulose ratio, and helical microfibrillar winding angles that allow sharp 180-degree folding without brittle rupture.",
        "summary_ta": "தாழை மடலின் ஸ்கிளீரன்கைமா நார்களின் உயர் இழுவிசை வலிமை (400-600 MPa), குறைவான லிக்னின்-செல்லுலோஸ் விகிதம் மற்றும் 180 பாகை கூர்மையாக மடிந்தாலும் முறியாத நெகிழ்வுத்தன்மையை வழங்கும் திருகு நுண்-செல்லுலோஸ் கட்டமைப்பு.",
        "sources": [
            "Textile Research Journal",
            "Plant Biomechanics Review",
            "Neithal Craft Ethno-archaeology"
        ],
        "content": "# Thazhai Vascular Bundle Lignocellulose Pliancy & Tensile Microstructure\n\nThe exceptional durability of *Thazham-Paai* mats—which withstand decades of rolling, walking, and wash cycles without tearing—stems from the micro-architecture of its vascular bundles:\n\n### 1. Cellular Morphology & High Cellulose Content\n- Pandanus leaf fibers consist of dense bundles of elongated sclerenchyma cells surrounding xylem and phloem vessels.\n- **Biochemical Makeup**:\n  - $\\alpha$-Cellulose: $62\\%-68\\%$ (provides high axial tensile strength).\n  - Hemicellulose: $18\\%-22\\%$ (provides elasticity and moisture-absorption capacity).\n  - Lignin: Only $10\\%-14\\%$ (substantially lower than wood fibers, preventing stiffness and brittle breakage).\n\n### 2. Microfibrillar Angle & Tensile Toughness\n- Inside the secondary cell wall, cellulose microfibrils are oriented at a gentle helical angle of $12^\\circ\\text{ to }18^\\circ$ relative to the fiber axis.\n- When tensile stress is applied during tight 24-plait weaving, the helical spirals untwist elastically, absorbing significant mechanical strain before experiencing plastic deformation.\n- **Tensile Strength**: Stripped screwpine ribbons exhibit tensile ratings between $450\\text{ and }650\\text{ MPa}$, rivaling commercial abaca and sisal fibers while remaining smooth and skin-friendly.\n\n### 3. Thermal & Moisture Regulating Dynamics\n- Each vascular strand possesses a hollow central lumen that acts as a microscopic capillary conduit.\n- When environmental humidity increases, the lumens absorb water vapor without surface dampness. In hot dry air, stored moisture transpires slowly, yielding sustained evaporative cooling against human skin.\n"
    },
    {
        "slug": "concept-sangam-neithal-seashore-fragrance-pollen-drift-and-cooling-aromatic-therapeutics",
        "file": "concept-sangam-neithal-seashore-fragrance-pollen-drift-and-cooling-aromatic-therapeutics.md",
        "category": "concept",
        "name_en": "Sangam Neithal Seashore Fragrance, Pollen Drift & Cooling Aromatic Therapeutics",
        "name_ta": "சங்க நெய்தல் கடற்கரை நறுமணம், தாழை மகரந்தக் காற்று மற்றும் குளிர்ச்சி நறுமண மருத்துவம்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "neithal",
        "summary_en": "The cultural geography and therapeutic paradigm of the maritime Neithal landscape in Sangam poetics, where sea breezes carrying fragrant screwpine pollen and Keora vapors symbolize separation, longing, and maritime cooling therapy against tropical fever and pitta imbalance.",
        "summary_ta": "சங்க இலக்கியத்தில் நெய்தல் நிலத்தின் குறியீடான தாழம்பூ மகரந்தக் காற்றும், கடலலையின் நறுமணமும்; பிரிவுத் துயரை ஆற்றுதல், வெப்பக் கொதிப்பைத் தணித்தல் மற்றும் பித்த நோய்களைக் குணப்படுத்தும் குளிர்ச்சி நறுமண மருத்துவ மரபு.",
        "sources": [
            "Natrinai 74",
            "Ahananuru 130",
            "Siddha Materia Medica (Gunapadam)"
        ],
        "content": "# Sangam Neithal Seashore Fragrance, Pollen Drift & Cooling Aromatic Therapeutics\n\nIn the classical Tamil *Ainthinai* landscape framework, the maritime *Neithal* tract is defined by the evocative visual and olfactory presence of flowering screwpine hedges (*தாழை வேலி*):\n\n### 1. Poetic Landscape Symbolism (*உரிப்பொருள்*)\n- In Sangam poetry, *Thazhai* represents the maritime edge where land yields to the surf. The pale ivory spathes bursting through sharp green thorns mirror the inner agony of love in separation (*இரங்கலும் இரங்கல் நிமித்தமும்*).\n- When the evening sea gale (*கொண்டல் காற்று*) blows inland across the Pichavaram backwaters and Poompuhar shores, it carries the golden pollen and sweet ether of *Pandanus* blossoms deep into coastal settlements, intoxicating wayfarers and lovers alike.\n\n### 2. Traditional Siddha Cooling Therapeutics\n- **Gunapadam Classification**:\n  - *Taste (Suvai)*: Sweet (*Inippu*) with an astringent (*Thuvarppu*) finish.\n  - *Potency (Veeriyam)*: Pronounced cold (*Seetha Veeriyam*).\n  - *Post-digestive effect (Pirivu)*: Sweet (*Inippu*).\n- Prescribed in Siddha formulations to mitigate acute thermal stress, sunstroke, headaches (*Pitta-Vatham*), and eye burning sensations.\n- Infusions of Keora flower water (*Thazham-Poo Theneer*) were consumed as natural cardiac tonics and refreshing summer coolers in temple celebrations and royal banquets.\n"
    },
    {
        "slug": "institution-neithal-parathavar-flower-gatherers-attar-merchants-and-weaving-cottage-guilds",
        "file": "institution-neithal-parathavar-flower-gatherers-attar-merchants-and-weaving-cottage-guilds.md",
        "category": "institution",
        "name_en": "Neithal Parathavar Flower-Gatherers, Attar Merchants & Weaving Cottage Guilds",
        "name_ta": "நெய்தல் பரதவர் பூப் பறிப்போர், அத்தர் வணிகர் மற்றும் தழம்பாய் நெசவுக் குடிசைக் கூட்டமைப்புகள்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "neithal",
        "summary_en": "Socio-economic organization of coastal coastal Parathavar and artisanal communities along the Coromandel coast, governing dawn screwpine flower foraging concessions, still-master guilds (Gandhika / Attar-Kaarar), and household women's mat plaiting collectives.",
        "summary_ta": "சோழ மண்டலக் கடற்கரையில் தாழம்பூப் பறிக்கும் உரிமை, வாசனைத் தைலம் வடித்தெடுக்கும் காந்திகர்/அத்தர் வணிகக் குழுக்கள் மற்றும் தாழம்பாய் பின்னலில் ஈடுபட்ட உழைக்கும் பெண்களின் குடிசைத் தொழிற்கூட்டமைப்புகளின் கட்டமைப்பு.",
        "sources": [
            "Silappadikaram 5.14-18 (Puhar Gandharvas)",
            "South Indian Inscriptions Vol. XIV",
            "Neithal Artisanal Ethnography"
        ],
        "content": "# Neithal Parathavar Flower-Gatherers, Attar Merchants & Weaving Cottage Guilds\n\nThe economic lifecycle of screwpine products linked estuarine hunter-foragers, domestic craftswomen, and elite mercantile networks into a vibrant coastal economy:\n\n### 1. Flower Foraging Collectives (*பூப்பறிப்போர்*)\n- Coastal *Parathavar* youth navigated shallow lagoons and mangrove creeks at 3:00 AM in dugout canoes (*Vallams*), venturing into dense, spine-laden coastal thickets where wild screwpine grows.\n- Strict customary territorial boundaries (*பங்கு உரிமை*) governed which lagoon channels belonged to specific fishing hamlets, ensuring sustainable pruning that stimulated repeated sprouting of new vegetative stems.\n\n### 2. Women's Domestic Weaving Collectives (*பாய் நெய்யும் மகளிர் குழு*)\n- While men were at sea fishing or harvesting flowers, village women formed cottage plaiting circles in shaded courtyards.\n- Grandmothers, mothers, and daughters collaborated on complex 24-plait bridal mats. A single master mat could demand 15 to 25 days of meticulous hand plaiting.\n- The women held independent control over mat trade revenue, selling to traveling mercantile guilds (*Manigramam* and *Valanjiyar*) at coastal weekly shandies (*சந்தை*).\n\n### 3. The Gandhika Guilds (*நறுமண வணிகக் காந்திகர்*)\n- Mentioned prominently in the Sangam epic *Silappadikaram* as selling fragrant powders, attars, and paste blocks along the broad streets of Kaveripattinam (Poompuhar).\n- The *Gandhika* guild financed copper hydrodistillation stills, provided advances of raw sandalwood oil to distillers, and packaged distilled Keora oils for export to Rome, Arabia, and Southeast Asia.\n"
    },
    {
        "slug": "place-pichavaram-ancient-neithal-thazhai-screwpine-and-keora-attar-haven",
        "file": "place-pichavaram-ancient-neithal-thazhai-screwpine-and-keora-attar-haven.md",
        "category": "place",
        "name_en": "Pichavaram: Ancient Neithal Thazhai Screwpine Groves, Keora Attar & Mat Weaving Haven",
        "name_ta": "பிச்சாவரம் - பண்டைய நெய்தல் தாழை மரக் காடுகள், தாழம்பூ அத்தர் மற்றும் பாய் நெசவுத் தளம்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "neithal",
        "summary_en": "Vast mangrove estuary and sand-spit wetland between the Vellar and Coleroon rivers in Cuddalore district, celebrated since Sangam antiquity for impenetrable wild Pandanus odorifer thickets, dawn Keora blossom harvesting, and coastal mat-plaiting cottage industries.",
        "summary_ta": "கடலூர் மாவட்டத்தில் வெள்ளாறு மற்றும் கொள்ளிடம் நதிகளின் முகத்துவாரத்தில் அமைந்துள்ள மாபெரும் சதுப்புநிலக் காடு; சங்க காலம் தொட்டே தாழைப் புதர்கள், அதிகாலை தாழம்பூ பறிப்பு, நறுமண அத்தர் வாலைவடிப்பு மற்றும் தாழம்பாய் நெசவுக்குப் புகழ்பெற்ற நெய்தல் தளம்.",
        "sources": [
            "Pattinappalai 110-120",
            "Archaeological Survey of Tamil Nadu (Pichavaram/Porto Novo)",
            "National Wetland Inventory"
        ],
        "content": "# Pichavaram: Ancient Neithal Thazhai Screwpine Groves, Keora Attar & Mat Weaving Haven\n\nSituated at `lat 11.4320, lng 79.7820` on the pristine estuarine delta where the **Vellar** and **Kollidam (Coleroon)** rivers merge into the Bay of Bengal, **Pichavaram** represents the quintessential *Neithal* coastal wetland ecosystem:\n\n### 1. Coastal Geography & Hydrological Sanctuary\n- **Inter-Tidal Sand Spits & Mangrove Canals**: Covering over 1,100 hectares across more than 4,400 intricate waterways and 50 sand islands, Pichavaram features a unique salinity gradient where freshwater river pulses collide with daily oceanic tides.\n- **The Screwpine Dune Fringe**: Along the outer maritime sand barrier separating the mangrove channels from the high-energy surf of the Bay of Bengal, impenetrable thickets of **Pandanus odorifer** form the primary coastal dune defense, preventing storm surge erosion and anchoring shifting sands.\n\n### 2. Historical & Artisanal Prominence\n- **Proximity to Ancient Poompuhar & Parangipettai**: Located just north of the Sangam Chola capital of Kaveripattinam and immediately south of the historic port of Parangipettai (Porto Novo), Pichavaram was the primary supply depot for fresh *Thazhambu* blossoms transported daily to temple sanctums of Chidambaram Nataraja Temple and royal perfumeries.\n- **Centuries of Mat-Plaiting Excellence**: Village settlements skirting the mangrove rim—such as Killai, Kanakarapattu, and Mudasalodai—harbor unbroken lineages of master weavers who transform wild screwpine leaves into world-famous ivory *Thazham-Paai* mats.\n"
    },
    {
        "slug": "text-sangam-neithal-corpus-kuruntokai-and-natrinai-on-fragrant-thazhai-and-mats",
        "file": "text-sangam-neithal-corpus-kuruntokai-and-natrinai-on-fragrant-thazhai-and-mats.md",
        "category": "text",
        "name_en": "Sangam Neithal Corpus: Kuruntokai & Natrinai on Fragrant Thazhai, Pollen Winds & Mats",
        "name_ta": "சங்க நெய்தல் இலக்கியம் - குறுந்தொகை மற்றும் நற்றிணையில் மணக்கும் தாழை, மகரந்தக் காற்று மற்றும் பாய்கள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Classical Tamil poetic verses from Kuruntokai, Natrinai, and Ahananuru depicting seaside screwpine hedges (thazhai veli), blossoming ivory spathes resembling swans, sweet intoxicating pollen drift across coastal hamlets, and tightly woven sleeping mats.",
        "summary_ta": "குறுந்தொகை, நற்றிணை மற்றும் அகநானூற்றுப் பாடல்களில் இடம்பெறும் நெய்தல் கடற்கரை தாழை வேலிகள், அன்னப்பறவையின் கழுத்தைப் போன்ற வெண்மையான தாழம்பூ மடல்கள், கடல்காற்றில் மிதக்கும் நறுமணம் மற்றும் மென்பாய்கள் பற்றிய இலக்கியப் பதிவுகள்.",
        "sources": [
            "Kuruntokai 163, 394",
            "Natrinai 74, 235",
            "Ahananuru 130, 160"
        ],
        "content": "# Sangam Neithal Corpus: Kuruntokai & Natrinai on Fragrant Thazhai, Pollen Winds & Mats\n\nThe poetry of the ancient Tamil *Sangam* anthology immortalizes *Thazhai* as both an aesthetic centerpiece and an ecological constant of the coastal seascape:\n\n### 1. Poetic Imagery of the Spathe (*தாழம்பூ உவமை*)\n- In **Natrinai 74**, the poet depicts the blooming screwpine bract as resembling the graceful ivory neck of an egret or swan resting on the dunes:\n  > *\"முடந்தை தாழை முகை வெண் குருகு என...\"*  \n  *(The curved screwpine spathes gleam on the shore like white egrets asleep in the dune grasses).*\n- The contrasting interplay between the razor-edged serrated leaves and the intoxicating, tender white interior serves as a frequent poetic metaphor for passionate love veiled behind strict societal guard.\n\n### 2. Pollen-Laden Coastal Gales (*தாது உதிர் காற்று*)\n- In **Kuruntokai 163**, the lover laments how the offshore sea breeze disperses yellow Keora pollen like golden flour over the salt-workers' huts:\n  > *\"நறுந் தாழை மலர் உதிர்ந்த தாது... உப்பமை சேரிப் பரக்கும் நல் நெய்தல்...\"*  \n  *(The fragrant pollen scattered from the blossoming Thazhai dusts the thatch of the salt-pan settlements across the vibrant Neithal coast).*\n\n### 3. Mat Weaving & Domestic Bedding in Ahananuru\n- **Ahananuru 160** describes the tranquil domestic rhythm of coastal fisherwomen plaiting fine sleeping mats from dried, thorn-stripped screwpine strips while waiting for the return of long-distance fishing boats at sunset.\n- The poems emphasize that sleeping upon a freshly plaited *Thazham-Paai* cooled the burning heat of the seaside climate, wrapping the slumberer in calming floral fragrance.\n"
    }
]

EDGES = [
    [
        "technology-pandanus-odorifer-frond-thorny-margin-paring-splitting-and-sun-bleaching",
        "produces",
        "artifact-thazham-paai-perfumed-sleeping-mats-betel-pouches-and-woven-baskets",
        "material_culture",
        "Sangam Era to Modern Era",
        "De-spined and sun-bleached fronds provide the core ribbon material for weaving perfumed sleeping mats and pouches",
        "Craft Observation"
    ],
    [
        "technology-thazham-paai-24-plait-twill-weaving-and-deg-bhapka-keora-attar-hydrodistillation",
        "utilizes",
        "artifact-copper-deg-receiver-bhapka-coir-insulation-and-sandalwood-keora-attar-flasks",
        "material_culture",
        "Sangam Era to Modern Era",
        "Hydrodistillation technology relies on copper degs, bamboo chonga vapor conduits, and bhapka receivers",
        "Ethnoarchaeology"
    ],
    [
        "technology-pandanus-odorifer-frond-thorny-margin-paring-splitting-and-sun-bleaching",
        "derives_from",
        "concept-thazhai-vascular-bundle-lignocellulose-pliancy-and-tensile-microstructure",
        "material_culture",
        "Sangam Era to Modern Era",
        "Ribbon splitting and folding rely on the low-lignin high-cellulose sclerenchyma tensile structure",
        "Biomechanical Analysis"
    ],
    [
        "technology-thazham-paai-24-plait-twill-weaving-and-deg-bhapka-keora-attar-hydrodistillation",
        "embodies",
        "concept-pandanus-odorifer-spathe-phenylethyl-alcohol-methyl-ether-volatile-chemistry",
        "material_culture",
        "Sangam Era to Modern Era",
        "Deg-bhapka hydrodistillation extracts and condenses 2-phenylethyl methyl ether volatile aroma compounds",
        "Chemical Analysis"
    ],
    [
        "place-pichavaram-ancient-neithal-thazhai-screwpine-and-keora-attar-haven",
        "cultivates",
        "technology-pandanus-odorifer-frond-thorny-margin-paring-splitting-and-sun-bleaching",
        "material_culture",
        "Sangam Era to Modern Era",
        "Pichavaram mangrove dunes provided abundant wild screwpine groves for harvesting and paring",
        "Geographical Survey"
    ],
    [
        "institution-neithal-parathavar-flower-gatherers-attar-merchants-and-weaving-cottage-guilds",
        "administers",
        "technology-thazham-paai-24-plait-twill-weaving-and-deg-bhapka-keora-attar-hydrodistillation",
        "material_culture",
        "Sangam Era to Modern Era",
        "Cottage guilds organized household mat plaiting while Gandhika guilds oversaw attar hydrodistillation",
        "Epigraphical Records"
    ],
    [
        "text-sangam-neithal-corpus-kuruntokai-and-natrinai-on-fragrant-thazhai-and-mats",
        "celebrates",
        "concept-sangam-neithal-seashore-fragrance-pollen-drift-and-cooling-aromatic-therapeutics",
        "material_culture",
        "Sangam Era",
        "Sangam poetry chronicles maritime pollen drift and cooling therapeutic aesthetics",
        "Literary Analysis"
    ],
    [
        "artifact-thazham-paai-perfumed-sleeping-mats-betel-pouches-and-woven-baskets",
        "retains",
        "concept-pandanus-odorifer-spathe-phenylethyl-alcohol-methyl-ether-volatile-chemistry",
        "material_culture",
        "Sangam Era to Modern Era",
        "Parenchyma cavities in woven mats trap trace Keora volatiles, yielding long-lasting natural room fragrance",
        "Material Science"
    ],
    [
        "institution-neithal-parathavar-flower-gatherers-attar-merchants-and-weaving-cottage-guilds",
        "operates_in",
        "place-pichavaram-ancient-neithal-thazhai-screwpine-and-keora-attar-haven",
        "material_culture",
        "Sangam Era to Modern Era",
        "Parathavar flower collectors and mat plaiting circles operated across the Pichavaram estuarine tract",
        "Historical Geography"
    ],
    [
        "artifact-copper-deg-receiver-bhapka-coir-insulation-and-sandalwood-keora-attar-flasks",
        "documented_in",
        "text-sangam-neithal-corpus-kuruntokai-and-natrinai-on-fragrant-thazhai-and-mats",
        "material_culture",
        "Sangam Era to Modern Era",
        "Classical Tamil literature documents coastal perfumery, attar vials, and floral distillates",
        "Literary Analysis"
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
