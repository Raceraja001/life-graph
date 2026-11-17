#!/usr/bin/env python3
"""
Harvester: Batch 50 - Ancient Tamil Bamboo & Rattan Basketry, Muram Winnowing Aerodynamics, Grain Silos & Medavar Plaiting Craft
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
        "slug": "text-sangam-literature-on-muram-winnowing-fans-kurinji-millet-chaffing-and-bamboo-baskets",
        "category": "text",
        "file": "text-sangam-literature-on-muram-winnowing-fans-kurinji-millet-chaffing-and-bamboo-baskets.md",
        "name_en": "Sangam Literary References to Muram Winnowing Fans, Kurinji Millet Chaffing & Bamboo Panniers",
        "name_ta": "சங்க இலக்கியங்களில் முறம் (சுளகு), குறிஞ்சித் தினைப் புடைப்பு மற்றும் மூங்கில் கூடைக் குறிப்புகள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "kurinji",
        "summary_en": "Classical Tamil poetic accounts in Purananuru, Kurinjippattu, Natrinai, Akananuru, and Malaipadukadam describing woven bamboo winnowing trays (muram / chulagu), Kurinji hill women winnowing red foxtail millet (thinai) on sun-warmed rock ledges, and the famous Purananuru heroism motif of driving off a tiger with a muram.",
        "summary_ta": "புறநானூறு, குறிஞ்சிப்பாட்டு, நற்றிணை, அகநானூறு மற்றும் மலைபடுகடாம் ஆகிய சங்க நூல்களில் மூங்கில் முறம் (சுளகு), பாறைகளில் தினை புடைக்கும் குறமகளிரின் பாடல்கள் மற்றும் முறத்தால் புலி ஓட்டிய வீரத்தாய் குறித்த இலக்கியச் சான்றுகள்.",
        "sources": [
            "Purananuru",
            "Kurinjippattu",
            "Natrinai",
            "Akananuru",
            "Malaipadukadam"
        ],
        "content": "# Sangam Literature on Muram Winnowing Fans, Millet Chaffing & Bamboo Baskets\n\nAcross the Sangam anthologies, the woven bamboo winnowing fan (**muram** or **chulagu**) and deep carrying basket (**vatti** / **koodai**) appear both as indispensable agro-processing tools and as potent poetic symbols of domestic vigilance and martial courage:\n\n**Poetic & Textual Attestations (Cited by Title):**\n- **Purananuru (The Warrior Woman & the Muram)**: In celebrated *Kanchi* and *Thumbai* heroic verses of *Purananuru*, the poet compares the broad, resonant ear of a war elephant to a bamboo *muram* (*murach-chevi yanai*), while folk-heroic memory immortalizes the *Maravar* woman who, while winnowing red millet in her courtyard, struck and chased away a prowling tiger with naught but the bamboo *muram* in her hand.\n- **Natrinai, Akananuru & Malaipadukadam (Kurinji Thinai Processing)**: Hill women (*Kurத்தியர்*) pound harvested foxtail millet (*thinai*) and mountain paddy (*aivana-nel*) in rock-cut mortars (*பாறை உரல்*) with ivory and sandalwood pestles, then toss the grain on plaited bamboo *muram* trays so the mountain breeze carries away the golden chaff.\n- **Kurinjippattu**: Mentions tightly woven bamboo flower baskets (*vatti*) and wide drying mats (*thatti*) used across hill settlements."
    },
    {
        "slug": "concept-muram-trapezoidal-aerodynamics-granular-brazil-nut-segregation-and-vortex-winnowing",
        "category": "concept",
        "file": "concept-muram-trapezoidal-aerodynamics-granular-brazil-nut-segregation-and-vortex-winnowing.md",
        "name_en": "Muram Trapezoidal Aerodynamics, Granular Percolation Physics & Multi-Mode Winnowing Kinematics",
        "name_ta": "முறத்தின் காற்றியக்கவியல் (Aerodynamics), துகள் பிரிப்பு இயற்பியல் மற்றும் புடைப்பு-கொழிப்பு இயக்கவியல்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Fluid mechanics and granular matter physics of the wedge-shaped Tamil winnowing tray (muram): how the deep boxed rear corners and tapered zero-lip front edge enable aerodynamic chaff ejection (pudaitthal), size-selective Brazil-nut percolation (kozhippu), and density-based stone separation (kal-arippu).",
        "summary_ta": "முறத்தின் பின்புற ஆழமான மூலைகளும் தட்டையான முன்பகுதியும் காற்றின் சுழற்சி மற்றும் ஈர்ப்பு விசை மூலம் உமி (புடைத்தல்), குறுணை (கொழித்தல்) மற்றும் கற்களைப் (கல் அரித்தல்) பிரிக்கும் இயற்பியல் கோட்பாடு.",
        "sources": [
            "Granular Matter Physics of Traditional Winnowing Trays",
            "Aerodynamics of Agricultural Chaff Separation",
            "Ethnographic Mechanics of South Indian Post-Harvest Tools"
        ],
        "content": "# Muram Trapezoidal Aerodynamics & Granular Segregation Physics\n\nUnlike circular flat sieves, the Tamil **muram** (*chulagu*) is an asymmetric, open-fronted trapezoidal scoop whose geometry—two deep $8\\text{--}10\\text{ cm}$ rear corner pockets tapering down to a flat, zero-lip front tongue—functions as a three-mode mechanical classifier:\n\n**1. Aerodynamic Chaff Separation (*Pudaitthal* — Vertical Toss):**\n- When the operator snaps the *muram* upward at $30^\\circ\\text{--}45^\\circ$, the grain bed is launched into a parabolic trajectory while the downward return stroke of the flat front lip sheds a sharp **counter-rotating air vortex**.\n- Because terminal settling velocity scales as $v_t = \\sqrt{\\frac{2 m g}{\\rho_{air} A C_D}}$, dense whole rice/millet grains ($\\rho \\approx 1400\\text{ kg/m}^3$) fall straight back into the deep rear pocket, whereas flat, high-drag husks (*umi*, $\\rho \\approx 120\\text{ kg/m}^3$) and dust are entrained by the lip vortex and blown clear over the front edge.\n\n**2. Granular Percolation / Inverse Brazil-Nut Effect (*Kozhippu* — Orbital Shake):**\n- Tilting the *muram* laterally and executing a rhythmic horizontal figure-eight oscillation (*கொழித்தல்*) fluidizes the grain bed. Smaller broken grits (*kurunai* / *நொய்*) percolate downward through void spaces to contact the high-friction twill floor, migrating up-slope while larger whole grains (*arisi*) slide down-slope into a separate lobe.\n\n**3. Inertial Density Separation (*Kal-Arippu*):**\n- Short, asymmetric backward jerks exploit the higher static friction of angular quartz stones (*kal*) against the ridged bamboo weave, walking heavy grit toward the rear corners while smooth ovals of grain cascade forward."
    },
    {
        "slug": "concept-dendrocalamus-strictus-kal-moongil-vascular-bundle-mechanics-and-twill-anisotropy",
        "category": "concept",
        "file": "concept-dendrocalamus-strictus-kal-moongil-vascular-bundle-mechanics-and-twill-anisotropy.md",
        "name_en": "Kal-Moongil & Perumoongil Vascular Bundle Gradient, Silica Epidermis & Twill Plaiting Mechanics",
        "name_ta": "கல்மூங்கில் மற்றும் பெருமூங்கில் நார் கட்டமைப்பு, சிலிக்கா புறத்தோல் வலிமை மற்றும் பின்னல் விசை இயற்பியல்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Botanical materials science of Tamil basketry bamboos—Dendrocalamus strictus (kal-moongil) and Bambusa bambos (perumoongil / mullu-moongil): radial functionally graded distribution of sclerenchyma fibers and phytolith silica in the outer cortex (mel-pattai) vs inner parenchymatous pith, and biaxial stiffness of 2/2 and 3/1 twill weaves.",
        "summary_ta": "கல்மூங்கில் (Dendrocalamus strictus) மற்றும் முள் மூங்கிலின் (Bambusa bambos) வெளிப்புறப் பச்சைப் பட்டையில் உள்ள சிலிக்கா மற்றும் நார் அடர்த்தியின் இழுவிசை வலிமையும், குறுக்கு-நெடுக்கு பின்னலின் (Twill Weave) கட்டமைப்பு அறிவியலும்.",
        "sources": [
            "Anatomy and Mechanical Properties of Indian Bamboos (FRI Dehradun)",
            "Ethnobotany of Western Ghats Bamboo Species in Tamil Nadu",
            "Mechanics of Biaxial Twill-Woven Composite Shells"
        ],
        "content": "# Kal-Moongil Vascular Bundle Mechanics & Twill Plaiting Anisotropy\n\nTamil basket weavers (*Medavar* and *Kuravar*) select between two primary sympodial bamboo species based on culm wall thickness, internode length, and vascular bundle density:\n\n**1. Botanical Species & Functionally Graded Culm Wall:**\n- **Kal-Moongil (*Dendrocalamus strictus*)**: Grown on dry rocky *Kurinji/Mullai* hill slopes, its thick-walled, nearly solid culms possess high specific gravity ($\\rho \\approx 750\\text{--}850\\text{ kg/m}^3$), making it ideal for rigid load-bearing basket ribs (*சட்டம்*) and *muram* rim hoops.\n- **Perumoongil / Pottu-Moongil (*Bambusa bambos*)**: Tall, thorny riparian culms with long, straight internodes ($30\\text{--}45\\text{ cm}$) and flexible walls suited for peeling paper-thin plaiting ribbons (*நார் / பட்டை*).\n- **Radial Sclerenchyma Gradient**: Across the culm wall thickness, cellulose-rich sclerenchyma vascular bundles and amorphous **opal silica ($\\text{SiO}_2 \\cdot n\\text{H}_2\\text{O}$) phytoliths** are densely packed near the outer green epidermis (**mel-pattai**, tensile strength $>250\\text{ MPa}$), whereas the inner lumen wall (**ul-pattai / chovvu**) is rich in soft parenchyma. Weavers always orient the glossy, silica-armored *mel-pattai* face upward on the working surface of a *muram* to resist grain abrasion.\n\n**2. Biaxial Twill Plaiting ($2/2$ and $3/1$ Herringbone):**\n- Interlacing orthogonal splints in an over-two, under-two ($2/2$) or over-three, under-one ($3/1$) twill pattern creates diagonal ridges (*மூலைவிட்ட வரி*) that prevent shear buckling under heavy grain loads while providing micro-steps that trap stones during winnowing."
    },
    {
        "slug": "concept-cow-dung-red-earth-composite-sealing-and-thombai-bamboo-silo-hygroscopic-respiration",
        "category": "concept",
        "file": "concept-cow-dung-red-earth-composite-sealing-and-thombai-bamboo-silo-hygroscopic-respiration.md",
        "name_en": "Saanam-Semman Composite Slurry Sealing & Hygroscopic Respiration in Thombai Bamboo Silos",
        "name_ta": "பசுஞ்சாணம்-செம்மண் பூச்சு வேதியியலும் தொம்பை (குதிர்) மூங்கில் களஞ்சியங்களின் ஈரப்பதச் சமநிலையும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Biopolymer and clay-mineral composite chemistry of coating woven bamboo winnowing trays (muram) and cylindrical grain silos (thombai / kuthir) with cow dung (saanam), kaolinitic red earth (semman), and turmeric or neem paste: sealing inter-splint gaps against weevils while maintaining vapor permeability to prevent grain mold.",
        "summary_ta": "முறம் மற்றும் மூங்கில் தொம்பைகளில் பூசப்படும் பசுஞ்சாணம், செம்மண், மஞ்சள் மற்றும் வேப்பிலைக் கலவை, மூங்கில் இடுக்குகளை அடைத்து வண்டுகளைத் தடுப்பதோடு தானியங்களின் ஈரப்பதத்தைச் சமநிலைப்படுத்தும் அறிவியல்.",
        "sources": [
            "Traditional Grain Storage Structures of Tamil Nadu (TNAU Monograph)",
            "Materials Science of Cow-Dung and Clay Bio-Composites",
            "Entomology of Stored Product Protection in Rural India"
        ],
        "content": "# Saanam-Semman Composite Slurry Sealing & Thombai Silo Respiration\n\nBare plaited bamboo contains microscopic interstices ($0.2\\text{--}1.0\\text{ mm}$) between intersecting splints that can trap fine millet flour or admit egg-laying grain weevils (*Sitophilus oryzae*). Traditional Tamil craft resolves this through a two-phase bio-mineral matrix coating (**saanam-mezhuguthal**):\n\n**1. Organo-Clay Cross-Linking Mechanics:**\n- Fresh bovine dung (*pasu-saanam*) consists of undigested lignocellulosic grass micro-fibers ($1\\text{--}5\\text{ mm}$ long) suspended in a colloidal gel of mucoproteins, bile salts, and anionic polysaccharides.\n- When kneaded with sifted **red lateritic earth (*semman*)** or tank-bed clay (*களிமண்*), turmeric powder, and neem leaf extract, the humic and mucoprotein polymers intercalate between kaolinite/illite clay platelets. Upon drying over the flexible bamboo lattice, the cellulose micro-fibers bridge shrinkage cracks, yielding an elastic, non-flaking skin that flexes with the *muram* during vigorous tossing.\n\n**2. Hygroscopic Breathing in Thombai Grain Silos:**\n- Unlike sweat-inducing plastic drums or sheet-metal bins where day-night temperature swings condense water droplets on the inner wall and trigger *Aspergillus* aflatoxin spoilage, a cow-dung-and-mud-plastered bamboo **thombai** (*kuthir*) acts as a hygroscopic buffer—absorbing excess moisture vapor during monsoon humidity spikes and transpiring it outward when dry winds return."
    },
    {
        "slug": "technology-moongil-splitting-thumb-guarded-splint-gauging-and-herringbone-twill-plaiting",
        "category": "technology",
        "file": "technology-moongil-splitting-thumb-guarded-splint-gauging-and-herringbone-twill-plaiting.md",
        "name_en": "Moongil Culm Splitting, Thumb-Guarded Splint Calibration, Corner Folding & Rattan Rim Binding",
        "name_ta": "மூங்கில் பிளத்தல், பட்டை இழைத்தல், மூலை மடிப்புப் பின்னல் மற்றும் பிரம்பு விளிம்பு கட்டும் தொழில்நுட்பம்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Step-by-step craft engineering of Tamil bamboo basketry: water-curing culms to leach borer-attracting starch, radial splitting with a heavy vaangi-aruval billhook, drawing uniform 0.8 mm splints between blade and thumb-guard, folding 3D rear corners of a muram without cutting warps, and lashing dual rim hoops.",
        "summary_ta": "மூங்கிலை நீரில் ஊறவைத்து வண்டு அரிக்காமல் பதப்படுத்தி, வாங்கி அருவாளால் பிளந்து, சீரான பட்டைகளாக இழைத்து, முறத்தின் இரு பின் மூலைகளை மடித்துப் பின்னிப் பிரம்பால் விளிம்பு கட்டும் கைவினைத் தொழில்நுட்பம்.",
        "sources": [
            "Craft Documentation of Bamboo Basketry in Coimbatore & Salem Districts",
            "All India Handicrafts Board Monograph on South Indian Cane and Bamboo",
            "Traditional Woodworking and Basketry Tools of Tamil Nadu"
        ],
        "content": "# Moongil Culm Splitting, Splint Calibration & Rim Binding Technology\n\nTransforming a cylindrical $8\\text{ m}$ bamboo culm into a balanced, tension-locked *muram* or load-bearing *koodai* follows a rigorous five-stage artisanal sequence:\n\n**1. Culm Selection & Starch Leaching (*Moongil-Padappaduthuthal*):**\n- Culms are felled at $2\\text{--}3\\text{ years}$ of age during the waning moon (when sap sugars are lowest) and submerged in flowing stream water or mud ponds for $10\\text{--}15\\text{ days}$. Anaerobic leaching removes soluble sucrose and starch from the parenchyma, rendering the finished basket immune to powder-post beetles (*Dinoderus minutus*).\n\n**2. Radial Splitting & Thumb-Guarded Splint Peeling (*Pattai-Izhaitthal*):**\n- Nodal diaphragms (*கணு*) are knocked out and the culm is split radially into 8 or 16 staves using a heavy, curved-beak billhook (**vaangi-aruval**).\n- Sitting on the ground with the stave braced against the foot, the weaver draws the knife between the outer green cortex and inner pith, pulling each ribbon between the knife bevel and a thick leather or rag thumb-guard (*கட்டைவிரல் உறை*) to gauge uniform $0.8\\text{--}1.2\\text{ mm}$ thickness.\n\n**3. 3D Corner Folding & Rim Hooping (*Vilimbu-Kattuthal*):**\n- First, a flat rectangular twill mat (*தட்டு*) is plaited. To form the two deep rear pockets of a *muram* without cutting the splints, the weaver wets the mat, folds the two rear corners inward along $45^\\circ$ gusset pleats, and sandwiches the raw edges between two thick split-bamboo U-hoops (*சட்டம்*) lashed tightly in a figure-eight spiral stitch using split rattan (**pirambu**, *Calamus rotang*) or palmyra midrib fiber (*நார்*)."
    },
    {
        "slug": "technology-saanam-semman-slurry-plastering-and-cylindrical-thombai-granary-erection",
        "category": "technology",
        "file": "technology-saanam-semman-slurry-plastering-and-cylindrical-thombai-granary-erection.md",
        "name_en": "Saanam-Semman Slurry Plastering, Tamarind-Paste Sizing & Thombai Bamboo Granary Erection",
        "name_ta": "சாணம்-செம்மண் மெழுகுதல், புளியங்கொட்டைப் பசை பூச்சு மற்றும் மூங்கில் தொம்பைக் களஞ்சியம் அமைக்கும் நுட்பம்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Surface-finishing and granary-building techniques for woven bamboo structures: applying multi-coat cow-dung, red-ochre earth, and boiled tamarind-seed paste (puliyankottai-kanji) to harden winnowing trays and harvesting panniers, and erecting elevated cylindrical bamboo grain silos (thombai / kuthir) on stone plinths.",
        "summary_ta": "புதிய முறம் மற்றும் கூடைகளின் உழைப்பை நீட்டிக்கப் புளியங்கொட்டைப் பசை, பசுஞ்சாணம் மற்றும் செம்மண் கலந்து மெழுகும் முறையும், கருங்கல் ஆதாரத்தின் மீது உருளை வடிவ மூங்கில் தொம்பை அமைத்துத் தானியம் சேமிக்கும் தொழில்நுட்பமும்.",
        "sources": [
            "Rural Architecture and Granary Engineering of Tamil Nadu",
            "Post-Harvest Grain Storage Practices in Kongu & Pandya Nadu",
            "Ethnography of Domestic Maintenance Rituals in Tamil Villages"
        ],
        "content": "# Saanam-Semman Slurry Plastering & Cylindrical Thombai Granary Erection\n\nOnce a bamboo *muram*, *thatti*, or *thombai* silo leaves the weaver's hands, household women and farmhands execute a structural curing and assembly protocol before putting it into service:\n\n**1. Three-Coat Muram & Koodai Seasoning (*Mezhuguthal*):**\n- **Base Sizing Coat**: Boiled tamarind-seed kernel mucilage (*puliyankottai-podi kanji*) or rice-gruel starch mixed with a pinch of copper sulfate or neem oil is brushed into both faces of the raw bamboo weave, gluing intersecting splints so they cannot shift under load.\n- **Saanam-Semman Finish**: Fresh cow dung is macerated with water, strained through coir mesh to remove coarse chaff, and blended with fine red earth (*semman*) and auspicious yellow turmeric (*manjal*) for domestic *muram* trays. Swept across the tray in semicircular hand strokes and baked in hot sun for two days, it cures into a taut, drum-like, splinter-free surface.\n\n**2. Erecting the Cylindrical Thombai / Kuthir Silo:**\n- A giant continuous twill-woven bamboo mat ($1.5\\text{--}2.5\\text{ m}$ high, $3\\text{--}5\\text{ m}$ circumference) is rolled into a vertical cylinder, overlap-stitched with coir rope, and hoisted onto four dressed granite pillar stones (*குதிர்க்கல்*, $30\\text{ cm}$ above the floor to block rising damp and rat burrowing).\n- Both interior and exterior walls receive a $1.5\\text{ cm}$ coat of clay-straw-dung mortar; a small square sliding discharge shutter (*மடை வாய்*) at the base allows daily grain withdrawal while the top is sealed with dried *nochi* (*Vitex negundo*) and neem leaves beneath a mud-luted bamboo lid."
    },
    {
        "slug": "artifact-muram-winnowing-trays-kozhi-koodu-poultry-domes-and-valli-koodai-harvest-baskets",
        "category": "artifact",
        "file": "artifact-muram-winnowing-trays-kozhi-koodu-poultry-domes-and-valli-koodai-harvest-baskets.md",
        "name_en": "Muram Winnowing Trays, Valli-Koodai Harvest Panniers, Kozhi-Koodu Domes & Seer-Koodai Sets",
        "name_ta": "முறம் (சுளகு), வள்ளிக்கூடை, கோழிக்கூடு, தட்டுக்கூடை மற்றும் சீர்க்கூடை வகைகளின் பயன்பாட்டுத் தொகுப்பு",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Comprehensive artifact typology of Tamil bamboo and rattan basketry across agricultural, domestic, and ritual domains: trapezoidal muram winnowers, heavy-ribbed valli-koodai head-load panniers, open-hexagonal kozhi-koodu poultry domes, shallow thattu-koodai flower trays, and dyed wedding seer-muram sets.",
        "summary_ta": "தமிழர் வேளாண்மை மற்றும் இல்லற வாழ்வில் பயன்படும் மூங்கில் பொருட்கள்: தானியம் புடைக்கும் முறம், தலைச்சுமை வள்ளிக்கூடை, காற்றோட்டமான கோழிக்கூடு, பூக்கூடை மற்றும் திருமணச் சீர்வரிசை முறங்கள்.",
        "sources": [
            "Census of India 1961: Handicrafts and Artisans of Madras State (Bamboo Basketry)",
            "Material Culture of Tamil Agriculture",
            "Government Museum Chennai Ethnology Gallery Catalog"
        ],
        "content": "# Muram Winnowing Trays, Valli-Koodai Panniers, Kozhi-Koodu Domes & Seer-Koodai\n\nTamil bamboo plaiting encompasses over twenty specialized container geometries tailored to distinct mechanical loads and airflow requirements:\n\n**Artifact Typology:**\n1. **Muram / Chulagu (Trapezoidal Winnowing Tray)**: Standard domestic dimensions measure $55\\text{ cm}$ length, $42\\text{ cm}$ rear width tapering to $35\\text{ cm}$ front width, with $9\\text{ cm}$ deep rear corner walls. A miniature version (**Siru-Muram** / **Podisu-Muram**) is woven for children's play and spice cleaning, while an oversized heavy-gauge **Kala-Muram** is used on threshing floors to winnow paddy against the wind (*தூற்றுதல்*).\n2. **Valli-Koodai & Mann-Koodai (Head-Load Panniers)**: Hemispherical bowls reinforced with 12 to 16 thick radial *kal-moongil* ribs (*நெட்டு*), engineered to carry $25\\text{--}35\\text{ kg}$ of harvested millet ears, cotton bolls, or tank silt on a worker's head without bottom sagging.\n3. **Kozhi-Koodu (Conical Open-Lattice Poultry Coop)**: Woven with wide hexagonal or diamond apertures ($3\\text{--}4\\text{ cm}$ mesh) from thick thorny-bamboo staves, inverted at dusk over brooding hens and chicks with a heavy stone atop the apex to exclude civets, mongooses, and snakes while ensuring cross-ventilation.\n4. **Seer-Muram & Thattu-Koodai (Auspicious Wedding Trays)**: Finely plaited trays dyed with bands of turmeric yellow, sappanwood red, and emerald green, used to present *thamboolam*, silk sarees, fruit, and *manjal-kungumam* during betrothals and *Pongal*."
    },
    {
        "slug": "artifact-vaangi-aruval-splitting-knives-pirambu-rattan-lashings-and-thombai-bamboo-silos",
        "category": "artifact",
        "file": "artifact-vaangi-aruval-splitting-knives-pirambu-rattan-lashings-and-thombai-bamboo-silos.md",
        "name_en": "Vaangi-Aruval Splitting Billhooks, Pirambu Rattan Lashings, Rim Awls & Thombai Grain Silos",
        "name_ta": "வாங்கி அருவாள், பிரம்பு நார், துளை ஊசி மற்றும் பெருந்தானிய மூங்கில் தொம்பைக் களஞ்சியங்கள்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Specialized tool kit of the Medavar/Kuravar bamboo artisan and monumental farm storage structures: forward-curved high-carbon steel vaangi-aruval splitting knives, wooden radial cleaving wedges, iron lacing awls, flexible Calamus rotang (pirambu) binding strips, and 100-bag bamboo thombai silos.",
        "summary_ta": "மூங்கில் கைவினைஞரின் கருவிகளும் பெருங்களஞ்சியங்களும்: மூங்கில் பிளக்கும் வாங்கி அருவாள், விளிம்பு கட்டும் பிரம்பு நார், இரும்புத் தையல் ஊசி மற்றும் நூறு மூட்டை நெல் சேமிக்கும் பிரம்மாண்ட மூங்கில் தொம்பைகள்.",
        "sources": [
            "Traditional Blacksmithing & Craft Knives of Tamil Nadu",
            "Forestry and Rattan (Calamus rotang) Resources of Southern India",
            "Indigenous Grain Storage Systems of Kongu Nadu"
        ],
        "content": "# Vaangi-Aruval Splitting Knives, Pirambu Lashings & Thombai Grain Silos\n\nRemarkably, the entire repertoire of Tamil bamboo basketry and monumental silo construction is executed using a compact, portable toolkit and three structural raw materials:\n\n**1. The Weaver's Toolkit:**\n- **Vaangi-Aruval / Moongil-Aruval (Curved Billhook)**: Forged by local blacksmiths with a thick, heavy spine ($6\\text{--}8\\text{ mm}$), a broad belly for radial impact splitting, and a hooked beak (*மூக்கு*) that prevents the blade from slipping out of the bamboo culm cleft. The single-bevel or asymmetric edge allows controlled peeling of $0.5\\text{ mm}$ splints without diving into the grain.\n- **Thoola-Oosi (Rim-Lacing Awl) & Marak-Kuzhavi (Mallet)**: A tapered iron bodkin mounted in a hardwood handle used to pierce narrow slots below the *muram* rim hoop so split rattan lashings can be threaded through, paired with a wooden beater for compacting weft splints tightly together.\n\n**2. Pirambu (*Calamus rotang*) Lashing & Thombai Silos:**\n- **Pirambu Rattan Strips**: Unlike bamboo, which snaps if bent sharply across its grain, the solid climbing stem of rattan (*pirambu*) possesses uniform vascular distribution, allowing peeled rattan ribbons to be tied in tight knots around basket rims.\n- **Thombai / Pattarai-Kuthir**: Standing $1.8\\text{--}2.5\\text{ m}$ tall in the shaded *thinnai* or granary room (*களஞ்சிய அறை*), these woven bamboo-and-mud cylinders preserve seed paddy (*விதை நெல்*) at $>92\\%$ germination viability for two full years."
    },
    {
        "slug": "institution-medavar-and-kuravar-bamboo-plaiting-guilds-and-malai-moongil-forest-coupes",
        "category": "institution",
        "file": "institution-medavar-and-kuravar-bamboo-plaiting-guilds-and-malai-moongil-forest-coupes.md",
        "name_en": "Medavar & Kuravar Bamboo-Plaiting Guilds, Forest Moongil Coupes & Ritual Seer-Muram Shares",
        "name_ta": "மேதவர் மற்றும் குறவர் மூங்கில் பின்னல் குடியினர், மலை மூங்கில் வெட்டுரிமை மற்றும் சடங்கு முறைமைப் பங்குகள்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Socio-economic and ritual institutions of hereditary bamboo-weaving communities in Tamil Nadu (Medavar / Mahendra, Malai-Kuravar, and Paraiyar artisans): rotational forest bamboo harvesting norms, cooperative family weaving workshops, weekly sandhai market circuits, and customary grain shares (sudhanthiram) for supplying wedding and temple baskets.",
        "summary_ta": "மூங்கில் கைவினைத் தொழிலில் ஈடுபடும் மேதவர் (மகேந்திரர்) மற்றும் குறவர் சமூகத்தினரின் கூட்டுறவுப் பணிமுறை, மலை மூங்கில் சேகரிப்பு விதிகள், வாரச் சந்தை வணிகம் மற்றும் திருமணங்களுக்குச் சீர் முறம் வழங்கிப் பெறும் அறுவடை நெல் பங்கு.",
        "sources": [
            "Castes and Tribes of Southern India (Thurston: Medara / Medavar & Kurava)",
            "Coimbatore & North Arcot District Manuals (Forestry & Village Artisans)",
            "Customary Jajmani / Mirasi Rights in Rural Tamil Nadu"
        ],
        "content": "# Medavar & Kuravar Bamboo-Plaiting Guilds & Ritual Seer-Muram Tenures\n\nBamboo and rattan craft in Tamil Nadu is anchored by specialized hereditary artisan communities—principally the **Medavar** (*Medara / Mahendra*), **Malai-Kuravar** (*Koodai-Kuravar*), and rural basketry guilds—whose livelihoods bridge *Kurinji* forest ecology and *Marutham* agrarian villages:\n\n**1. Sustainable Clump Management (*Moongil-Vettu Norm*):**\n- Traditional forest harvesters observe strict clump-thinning ethics: never clear-felling a bamboo clump (*மூங்கில் புதர்*), leaving all first-year tender shoots (*குருத்து*) untouched to nourish the rhizome mat, and cutting only mature 3-year interior culms above the second node so rainwater does not rot the underground rootstock.\n\n**2. Household Workshop Division & Sandhai Circuits:**\n- Men travel to hill coupes to fell, bundle, and cart green culms and split heavy structural ribs, while women and elders execute high-speed twill plaiting of *muram* trays, *valli-koodai* baskets, and *kozhi-koodu* coops, producing 6 to 10 trays per household daily ahead of the *Thai* harvest and *Chithirai* marriage seasons.\n\n**3. Ritual Auspiciousness & Harvest Grain Shares (*Sudhanthiram*):**\n- In Tamil custom, a bamboo *muram* is never referred to as \"empty\" or stepped over with feet; every wedding (*kalyanam*), ear-piercing (*kaadhu-kuthu*), and *Valaikappu* requires a brand-new pair of *Seer-Muram* delivered by the village basket-maker, who receives a statutory share of threshed paddy (*களம் அளப்பு*) and festive meals at the village threshing floor."
    },
    {
        "slug": "place-anaimalai-ancient-vettai-karan-pudur-bamboo-basketry-and-muram-haven",
        "category": "place",
        "file": "place-anaimalai-ancient-vettai-karan-pudur-bamboo-basketry-and-muram-haven.md",
        "name_en": "Anaimalai–Vettaikaranpudur: Ancient Western Ghats Foothill Bamboo Basketry & Muram Haven",
        "name_ta": "ஆனைமலை-வேட்டைக்காரன்புதூர் - மேற்குத் தொடர்ச்சி மலை அடிவார மூங்கில் கூடை மற்றும் முறம் பின்னல் தளம்",
        "era": "Early Medieval to Modern Era",
        "year_start": 700,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Historic foothill craft settlement cluster at Anaimalai and Vettaikaranpudur in Pollachi taluk, Coimbatore district (lat 10.5580, lng 76.9360, thinai: kurinji), situated at the gateway to the Topslip–Aliyar bamboo forests and renowned across Kongu Nadu and Kerala for its hereditary Medavar and Kuravar muram-weaving streets.",
        "summary_ta": "கோயம்புத்தூர் மாவட்டம் பொள்ளாச்சி அருகே ஆனைமலை மலைத்தொடர் அடிவாரத்தில் அமைந்துள்ள ஆனைமலை மற்றும் வேட்டைக்காரன்புதூர் (lat 10.5580, lng 76.9360, குறிஞ்சித் திணை): டாப்சிலிப்-ஆழியாறு மூங்கில் வளமும் பாரம்பரிய முறம், கூடை பின்னும் கைவினைஞர் வீதிகளும் நிறைந்த வரலாற்றுத் தளம்.",
        "sources": [
            "Coimbatore District Gazetteer (Anaimalai Forest Range & Cottage Industries)",
            "Working Plan for the Coimbatore South / Anaimalai Forest Division",
            "Ethnographic Survey of Kongu Nadu Bamboo Weavers"
        ],
        "content": "# Anaimalai–Vettaikaranpudur: Ancient Western Ghats Bamboo Basketry & Muram Haven\n\nSituated at `lat 10.5580, lng 76.9360` along the *Kurinji–Mullai* foothill ecotone of the Anaimalai range (Western Ghats) near Pollachi in Coimbatore district—watered by the Aliyar and Uppar mountain streams and bordering the famous Topslip–Sethumadai forest belt—the twin settlements of **Anaimalai** and **Vettaikaranpudur** form one of southern India's oldest and largest living hubs of bamboo basketry:\n\n**Ecological & Artisanal Distinction:**\n- **Anaimalai Moist-Deciduous Bamboo Corridor**: The monsoon-fed slopes of the Anaimalai hills (receiving both Southwest Palghat-Gap winds and Northeast rains) sustain dense, high-silica stands of *Dendrocalamus strictus* (*kal-moongil*), *Bambusa bambos* (*perumoongil*), and wild *Calamus* rattan (*pirambu*) prized for their long, knot-free internodes and high tensile elasticity.\n- **Weaving Streets & Pollachi Sandhai Hub**: Whole neighborhoods in Vettaikaranpudur, Anaimalai, Kottur, and Sarkarpathy operate as open-air bamboo workshops where hundreds of *Medavar* and *Kuravar* families split green culms, weave double-rimmed *Kongu Muram* winnowing trays, coconut-harvesting *valli-koodai* panniers, silk-rearing trays (*தட்டு*), and *thombai* granaries distributed through the historic Pollachi and Anaimalai weekly *sandhais* across Tamil Nadu and Palakkad."
    }
]

EDGES = [
    [
        "text-sangam-literature-on-muram-winnowing-fans-kurinji-millet-chaffing-and-bamboo-baskets",
        "describes",
        "artifact-muram-winnowing-trays-kozhi-koodu-poultry-domes-and-valli-koodai-harvest-baskets",
        "material_culture",
        "Sangam to Modern Era",
        "Purananuru, Natrinai, and Kurinjippattu celebrate the woven bamboo muram winnowing fan and vatti flower/grain baskets.",
        "Purananuru & Natrinai"
    ],
    [
        "text-sangam-literature-on-muram-winnowing-fans-kurinji-millet-chaffing-and-bamboo-baskets",
        "illustrates",
        "concept-muram-trapezoidal-aerodynamics-granular-brazil-nut-segregation-and-vortex-winnowing",
        "material_culture",
        "Sangam to Modern Era",
        "Sangam poems depict Kurinji women tossing pounded thinai millet on bamboo muram trays to separate golden chaff on mountain breezes.",
        "Akananuru & Malaipadukadam"
    ],
    [
        "concept-muram-trapezoidal-aerodynamics-granular-brazil-nut-segregation-and-vortex-winnowing",
        "governs_geometry_of",
        "artifact-muram-winnowing-trays-kozhi-koodu-poultry-domes-and-valli-koodai-harvest-baskets",
        "material_culture",
        "Sangam to Modern Era",
        "Counter-rotating front-lip air vortices and granular percolation physics dictate the deep rear corners and zero-lip front tongue of the muram.",
        "Granular Physics Studies"
    ],
    [
        "concept-dendrocalamus-strictus-kal-moongil-vascular-bundle-mechanics-and-twill-anisotropy",
        "underpins",
        "technology-moongil-splitting-thumb-guarded-splint-gauging-and-herringbone-twill-plaiting",
        "material_culture",
        "Sangam to Modern Era",
        "The radial gradient of silica-rich outer sclerenchyma fibers vs inner pith guides thumb-guarded splint peeling and 2/2 herringbone twill plaiting.",
        "Indian Bamboo Anatomy Monographs"
    ],
    [
        "concept-cow-dung-red-earth-composite-sealing-and-thombai-bamboo-silo-hygroscopic-respiration",
        "explains",
        "technology-saanam-semman-slurry-plastering-and-cylindrical-thombai-granary-erection",
        "material_culture",
        "Sangam to Modern Era",
        "Cross-linking between cow-dung lignocellulose/mucoproteins and kaolinite clay creates a breathable weevil-proof coat on muram trays and thombai silos.",
        "TNAU Storage Monograph"
    ],
    [
        "technology-moongil-splitting-thumb-guarded-splint-gauging-and-herringbone-twill-plaiting",
        "employs",
        "artifact-vaangi-aruval-splitting-knives-pirambu-rattan-lashings-and-thombai-bamboo-silos",
        "material_culture",
        "Sangam to Modern Era",
        "Radial culm splitting and rim hoop binding rely on the curved vaangi-aruval billhook, iron lacing awl, and split pirambu rattan.",
        "Handicrafts of Madras State"
    ],
    [
        "technology-moongil-splitting-thumb-guarded-splint-gauging-and-herringbone-twill-plaiting",
        "fabricates",
        "artifact-muram-winnowing-trays-kozhi-koodu-poultry-domes-and-valli-koodai-harvest-baskets",
        "material_culture",
        "Sangam to Modern Era",
        "Twill plaiting, 45-degree corner pleating, and double-hoop rim lashing produce durable muram winnowers and valli-koodai harvest baskets.",
        "Craft Documentation"
    ],
    [
        "technology-saanam-semman-slurry-plastering-and-cylindrical-thombai-granary-erection",
        "constructs",
        "artifact-vaangi-aruval-splitting-knives-pirambu-rattan-lashings-and-thombai-bamboo-silos",
        "material_culture",
        "Sangam to Modern Era",
        "Rolling giant twill bamboo mats onto granite plinth stones and plastering with clay-dung mortar constructs 100-bag thombai grain silos.",
        "Rural Architecture Studies"
    ],
    [
        "institution-medavar-and-kuravar-bamboo-plaiting-guilds-and-malai-moongil-forest-coupes",
        "practices",
        "technology-moongil-splitting-thumb-guarded-splint-gauging-and-herringbone-twill-plaiting",
        "material_culture",
        "Sangam to Modern Era",
        "Hereditary Medavar and Kuravar artisan families harvest mature 3-year forest culms and plait agricultural and wedding baskets.",
        "Thurston Castes and Tribes"
    ],
    [
        "institution-medavar-and-kuravar-bamboo-plaiting-guilds-and-malai-moongil-forest-coupes",
        "thrives_in",
        "place-anaimalai-ancient-vettai-karan-pudur-bamboo-basketry-and-muram-haven",
        "material_culture",
        "Early Medieval to Modern Era",
        "Medavar and Kuravar weaving clusters in Anaimalai and Vettaikaranpudur draw kal-moongil and pirambu from the Topslip–Aliyar foothills.",
        "Coimbatore District Gazetteer"
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
