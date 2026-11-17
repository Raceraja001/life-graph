#!/usr/bin/env python3
"""
Harvester: Batch 46 - Ancient Tamil Terracotta & Wooden Toys, Thalaiyatti Counterweight Dolls & Childhood Pedagogy
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
        "slug": "text-sangam-and-bhakti-literature-on-siru-ther-toy-carts-and-childhood-playthings",
        "category": "text",
        "file": "text-sangam-and-bhakti-literature-on-siru-ther-toy-carts-and-childhood-playthings.md",
        "name_en": "Sangam & Bhakti Literary References to Siru-Ther Toy Carts, Marappachi Dolls & Kilukiluppai Rattles",
        "name_ta": "சங்க மற்றும் பக்தி இலக்கியங்களில் சிறுதேர், மரப்பாச்சி பொம்மை மற்றும் கிலுகிலுப்பைக் குறிப்புகள்",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "marutham",
        "summary_en": "Classical Tamil poetic accounts in Kalittokai, Akananuru, Narrinai, Purananuru, and Periazhwar Tirumozhi (Pillai-Tamizh genre) describing children rolling miniature three-wheeled toy chariots (siru-ther), cradling carved wooden dolls (marappachi / vandal-pavai), and shaking seed-filled rattles (kilukiluppai).",
        "summary_ta": "கலித்தொகை, அகநானூறு, நற்றிணை, புறநானூறு மற்றும் பெரியாழ்வார் திருமொழி (பிள்ளைத்தமிழ்) ஆகிய நூல்களில் குழந்தைகள் உருட்டி விளையாடும் சிறுதேர், மரப்பாச்சி, வண்டல் பாவை மற்றும் கிலுகிலுப்பை பற்றிய இலக்கியக் குறிப்புகள்.",
        "sources": [
            "Kalittokai",
            "Akananuru",
            "Narrinai",
            "Purananuru",
            "Periazhwar Tirumozhi"
        ],
        "content": "# Sangam & Bhakti Literature on Siru-Ther Toy Carts and Childhood Playthings\n\nClassical Tamil poetry across the Sangam anthologies and Bhakti *Pillai-Tamizh* hymns preserves an intimate record of indigenous children's toys, their materials, and their domestic settings:\n\n**Sangam Poetic Attestations (Cited by Title):**\n- **Siru-Ther (Miniature Toy Chariots)**: Both *Kalittokai* and *Akananuru* depict toddlers in *Marutham* and *Neythal* courtyards pushing ornate miniature wooden and terracotta carts (*siru-ther* / *puthalvar uruttum siru-ther*) carved by master carpenters (*thachar*), leaving tiny wheel ruts across the threshold sand that soften a returning father's heart.\n- **Pavai & Marappachi Dolls**: *Narrinai* and *Purananuru* describe young girls fashioning alluvial clay figurines (*vandal-pavai*), nursing carved wooden dolls (*marappachi*), and feeding them imaginary meals in shaded verandahs.\n- **Bhakti Pillai-Tamizh Poetics**: In *Periazhwar Tirumozhi* and later *Pillai-Tamizh* treatises, the poet-saint celebrates the *Siru-Ther Paruvam* (stage of rolling the little chariot), alongside shaking resonant *kilukiluppai* rattles and staging miniature kitchen play (*siru-choru*)."
    },
    {
        "slug": "concept-thalaiyatti-bommai-weighted-hemisphere-center-of-mass-and-gimbal-oscillation",
        "category": "concept",
        "file": "concept-thalaiyatti-bommai-weighted-hemisphere-center-of-mass-and-gimbal-oscillation.md",
        "name_en": "Thanjavur Thalaiyatti Bommai Roly-Poly Center-of-Mass Restoration & Gimbal Nodding Mechanics",
        "name_ta": "தஞ்சாவூர் தலையாட்டிப் பொம்மையின் புவியீர்ப்பு மையச் சமநிலை மற்றும் ஊசல் அசைவு இயற்பியல்",
        "era": "Medieval to Modern Era",
        "year_start": 1000,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Rotational dynamics and rigid-body statics of the Thanjavur Thalaiyatti Bommai (bobblehead and roly-poly dolls): a dense clay-and-sand weighted hemispherical base lowers the center of mass below the geometric center of curvature, generating a self-righting gravitational torque, paired with wire-pivoted gimbal pendulums in four-piece nodding dancer dolls.",
        "summary_ta": "தஞ்சாவூர் தலையாட்டிப் பொம்மையின் அடிப்பகுதியில் கனமான களிமண் உருண்டை அமைத்துப் புவியீர்ப்பு மையத்தைத் தாழ்த்துவதால் சாய்ந்தாலும் மீண்டும் நிமிரும் இயற்பியல் தத்துவமும், நான்கு பாக நடனப் பொம்மையின் ஊசல் இயக்கமும்.",
        "sources": [
            "Thanjavur Bobblehead Doll Geographical Indication Dossier",
            "Mechanics of Self-Righting Roly-Poly Bodies",
            "Handicrafts of Tamil Nadu Ethnographic Survey"
        ],
        "content": "# Thanjavur Thalaiyatti Bommai: Center-of-Mass Restoration & Gimbal Oscillation\n\nThe *Thanjavur Thalaiyatti Bommai* embodies two distinct mechanical principles of low-damping harmonic oscillation engineered by deltaic clay-and-pulp artisans:\n\n**1. Roly-Poly Self-Righting Statics (*irumbu-nilai* / Counterweight Base):**\n- **Hemispherical Geometry**: The doll's base is molded as a smooth hemisphere of radius $R$, filled at the bottom with high-density river clay and lead/sand ballast while the upper torso is cast as an ultra-lightweight hollow paper-mache and tapioca-flour shell.\n- **Restoring Torque ($\\tau = -mgd\\sin\\theta$)**: Because the composite center of mass $G$ lies at a height $h < R$ strictly below the center of curvature $C$ of the hemispherical base, any angular displacement $\\theta$ shifts the line of action of gravity inward of the ground contact point, creating a positive restoring moment that rocks the doll back to vertical equilibrium—serving as a philosophical metaphor for resilience (*veezhnthalum ezhum*).\n\n**2. Multi-Link Gimbal Nodding Dolls (*Natya Bommai*):**\n- In four-part classical dancer dolls (head, torso, skirt, and pedestal), each hollow segment balances on a concealed U-bent brass or iron wire fulcrum with a hidden lower clay bob, allowing independent, low-friction coupled oscillations lasting several minutes after a gentle tap."
    },
    {
        "slug": "concept-sen-chandana-marappachi-medicinal-teething-dolls-and-navaratri-golu-pedagogy",
        "category": "concept",
        "file": "concept-sen-chandana-marappachi-medicinal-teething-dolls-and-navaratri-golu-pedagogy.md",
        "name_en": "Sen-Chandana Marappachi Red Sandalwood Medicinal Teething Dolls & Navaratri Golu Taxonomy",
        "name_ta": "செஞ்சந்தன மரப்பாச்சிப் பொம்மையின் மருத்துவக் குணங்களும் நவராத்திரி கொலு படிநிலைத் தத்துவமும்",
        "era": "Early Medieval to Modern Era",
        "year_start": 600,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Ethnomedical pharmacology and ritual pedagogy of unvarnished Pterocarpus santalinus (red sandalwood / sen-chandana) Marappachi dolls: maternal wedding gifts passed to teething infants for anti-inflammatory santalin and pterostilbene gum relief, and their inaugural placement atop the nine-tiered Navaratri Bommai Golu cosmological display.",
        "summary_ta": "ஈறு நமைச்சலைக் குணப்படுத்தும் செஞ்சந்தன (Pterocarpus santalinus) மரப்பாச்சிப் பொம்மையின் மூலிகை மருத்துவப் பயன்களும், நவராத்திரி ஒன்பது படிக் கொலுவில் உயிரினப் பரிணாமத்தை விளக்கும் கல்வி முறையும்.",
        "sources": [
            "Pharmacognosy of Pterocarpus santalinus (Red Sanders)",
            "South Indian Folk Toys & Ritual Material Culture",
            "Navaratri Bommai Golu Ethnographic Studies"
        ],
        "content": "# Sen-Chandana Marappachi Teething Pharmacology & Navaratri Golu Taxonomy\n\nIn traditional Tamil households, the geometric wooden *Marappachi* couple—carved as an unadorned naked bride and groom—serves simultaneously as a pediatric therapeutic instrument and a ritual heirloom:\n\n**1. Ethnomedical Teething Pharmacology (*Sen-Chandanam*):**\n- **Botanical Source**: Authentic *Marappachi* dolls are carved from dense, crimson heartwood of *Pterocarpus santalinus* (Red Sanders / *Sen-Chandanam* or *Karungali* ebony), completely free of synthetic paint or lacquer.\n- **Salivary Extraction during Dentition**: Handed down from a bride's wedding trousseau to her infant during the 5th to 10th month teething phase, the smooth, rounded hardwood geometry massages inflamed gingival tissue while infant saliva leaches trace amounts of santalin, pterostilbene, and astringent tannins—compounds with documented mucosal soothing, antimicrobial, and digestive properties.\n\n**2. Navaratri Bommai Golu Cosmological Pedagogy:**\n- Arranged on an odd number of stepped wooden tiers (*padi*, typically 5, 7, or 9), the *Golu* display teaches children ecological and evolutionary order: from single-sense flora and clay insects on the bottom steps, through village artisans, merchants (*Chettiar* dolls), and kings in the middle tiers, up to the ancestral *Marappachi* couple and divine forms at the apex."
    },
    {
        "slug": "concept-pillai-tamizh-developmental-stages-and-kinesthetic-childhood-toy-pedagogy",
        "category": "concept",
        "file": "concept-pillai-tamizh-developmental-stages-and-kinesthetic-childhood-toy-pedagogy.md",
        "name_en": "Pillai-Tamizh Ten-Stage Developmental Milestones & Kinesthetic Childhood Toy Pedagogy",
        "name_ta": "பிள்ளைத்தமிழ்ப் பத்துப் பருவ வளர்ச்சி நிலைகளும் குழந்தைகளின் புலன்-இயக்க விளையாட்டுக் கல்வியும்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Indigenous Tamil child-development framework aligning sensorimotor toy design with the ten developmental milestones (paruvam) codified in Pillai-Tamizh literature: auditory localization via kilukiluppai rattles, fine-motor grasp via marappachi dolls, bipedal gait stabilization with three-wheeled nada-vandi walkers, and social cognition through soppana-saman miniature utensils.",
        "summary_ta": "பிள்ளைத்தமிழ் இலக்கியத்தின் பத்துப் பருவ வளர்ச்சி நிலைகளுக்கு ஏற்ப வடிவமைக்கப்பட்ட கிலுகிலுப்பை, மரப்பாச்சி, முச்சக்கர நடைவண்டி மற்றும் சொப்புச் சாமான்களின் புலன்-இயக்கக் கல்வி முறை.",
        "sources": [
            "Panniru Pattiyal (Pillai-Tamizh Grammar)",
            "Meenakshi Ammai Pillai-Tamizh",
            "Indigenous Tamil Childhood Pedagogy & Motor Development"
        ],
        "content": "# Pillai-Tamizh Developmental Stages & Kinesthetic Toy Pedagogy\n\nClassical Tamil grammatical treatises (*Pattiyal* texts) divide early childhood (months 3 to 24+) into ten sequential developmental stages (*paruvam*), each matched by traditional toy-makers with calibrated sensorimotor instruments:\n\n**Milestone-to-Toy Biomechanical Mapping:**\n1. **3–5 Months (*Kappu, Senkeerai, Thaal*) — Auditory & Ocular Tracking**: Woven palmyra *olai-kilukiluppai* and wooden rattles suspended above the cradle (*thottil*) emit high-frequency seed clicks when kicked or batted, training binaural sound localization and visual convergence.\n2. **6–9 Months (*Sappani, Mutham, Varugai*) — Palmar Grasp & Dentition**: High-contrast lac-turned wooden dumbbells and *sen-chandana marappachi* dolls encourage bilateral hand transfer and soothe erupting incisors.\n3. **10–15 Months (*Ambuli,keel-nadai*) — Bipedal Equilibrium (*Nada-Vandi*)**: The three-wheeled hardwood push-walker (*nada-vandi* / *thirukkal-vandi*) with a long angled handle provides a stable triangular base of support, allowing toddlers to calibrate stride length and ankle proprioception without tipping.\n4. **16–24+ Months (*Siru-Parai, Siru-Ther, Siru-Choru*) — Roleplay & Fine Motor Coordination**: Pulling wheeled *siru-ther* carts and handling miniature *soppana-saman* kitchen vessels build pincer dexterity and cooperative social schemas."
    },
    {
        "slug": "technology-gadilam-alluvial-clay-press-molding-and-tapioca-paper-mache-shell-casting",
        "category": "technology",
        "file": "technology-gadilam-alluvial-clay-press-molding-and-tapioca-paper-mache-shell-casting.md",
        "name_en": "Gadilam Alluvial Clay Levigation, Two-Piece Press-Molding & Tapioca-Paper-Mache Shell Casting",
        "name_ta": "கெடிலம் ஆற்று வண்டல் மண் பதப்படுத்துதல், இரு-பாக அச்சு வார்ப்பு மற்றும் கூழ்-பொம்மைத் தொழில்நுட்பம்",
        "era": "Early Medieval to Modern Era",
        "year_start": 700,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Ceramic and composite manufacturing processes of Tamil doll artisans: levigating plastic Gadilam and Kaveri alluvial clay, pressing damp slabs into two-piece fired terracotta or lime-plaster molds (achu), laminating lightweight paper-pulp, tapioca starch (javvarisi), and fenugreek paste shells, and painting with mineral pigments.",
        "summary_ta": "கெடிலம் மற்றும் காவிரி வண்டல் மண்ணைச் சலித்துப் பதப்படுத்தி, இரு-பாகச் சுடுமண் அச்சுகளில் வார்த்து, மரவள்ளிக்கிழங்கு பசை மற்றும் காகிதக் கூழ் கொண்டு இலகுவான பொம்மைகள் செய்யும் தொழில்நுட்பம்.",
        "sources": [
            "Panruti & Thanjavur Terracotta Craft Manuals",
            "Traditional Ceramic Molds of South India",
            "All India Handicrafts Board Survey on Tamil Nadu Toys"
        ],
        "content": "# Gadilam Alluvial Clay Press-Molding & Tapioca-Paper-Mache Shell Casting\n\nArtisans along the Gadilam (Panruti) and Kaveri (Thanjavur) river plains perfected two complementary molding technologies for figurine and bobblehead production:\n\n**1. Alluvial Clay Preparation & Two-Piece Press-Molding (*Achu-Bommai*):**\n- **Levigation & Tempering**: Silty riverine clay (*vandal-mann*) is slaked in pits, sieved to remove calcareous nodules, and wedged with fine river sand and paddy-husk ash to minimize drying shrinkage below 6%.\n- **Bivalve Terracotta & Lime Molds**: Master sculptors carve a solid prototype (*thai-bommai*), from which front and back negative molds (*achu*) are cast in hard-fired porous terracotta or lime-gypsum plaster. Artisans dust the mold interior with dry ash, press thin clay pancakes into both halves, score and lute the seam with slip, and low-fire the hollow figure in clamp kilns (*soolai*).\n\n**2. Composite Paper-Mache & Tapioca Shell Lamination (*Koozh-Bommai*):**\n- For ultra-light upper shells of *Thalaiyatti* and *Golu* dolls, macerated waste paper pulp is boiled with tapioca flour (*maravalli-maavu* / *javvarisi*), ground fenugreek seeds (*vendhayam* mucilage binder), and a pinch of copper sulfate (*mayil-thutham* insect repellent), pressed into 2 mm shells inside molds, sun-cured, coated with white kaolin-tamarind-seed gesso (*vilam-pisin*), and painted with mineral earths."
    },
    {
        "slug": "technology-palmyra-leaf-olai-kilukiluppai-braiding-and-wooden-nada-vandi-joinery",
        "category": "technology",
        "file": "technology-palmyra-leaf-olai-kilukiluppai-braiding-and-wooden-nada-vandi-joinery.md",
        "name_en": "Palmyra-Leaf Olai-Kilukiluppai Polyhedral Braiding & Lathe-Turned Nada-Vandi Walker Joinery",
        "name_ta": "பனையோலைக் கிலுகிலுப்பை பின்னல் கலையும் கடைசல் மர நடைவண்டித் தச்சுத் தொழில்நுட்பமும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Basketry and woodworking craft of infant playthings: folding cured Borassus flabellifer (palmyra) leaf ribbons into seamless hollow polyhedral rattles (olai-kilukiluppai) enclosing sounding seeds, and lathe-turning (kadaisal) country-wood three-wheeled toddler walkers (nada-vandi) coated with non-toxic shellac (arakku).",
        "summary_ta": "பதப்படுத்தப்பட்ட பனையோலைக் கீற்றுகளை முப்பரிமாணப் பெட்டகமாகப் பின்னி உள்ளே விதைகள் இட்டுக் கிலுகிலுப்பை செய்யும் கலையும், கடைசல் மரத்தில் அரக்கு வண்ணம் பூசிய நடைவண்டி செய்யும் தச்சு நுட்பமும்.",
        "sources": [
            "Palmyra Palm Crafts of Tirunelveli & Ramanathapuram",
            "Traditional Wood Turning & Lacquerware of Tamil Nadu",
            "Ethnobotany of Borassus flabellifer in Tamil Material Culture"
        ],
        "content": "# Palmyra-Leaf Olai-Kilukiluppai Braiding & Nada-Vandi Joinery\n\nTwo everyday infant apparatuses—the woven palm-leaf rattle and the three-wheeled wooden walker—demonstrate zero-metal, child-safe structural engineering:\n\n**1. Olai-Kilukiluppai Polyhedral Weaving (*Borassus flabellifer*):**\n- **Ribbon Preparation**: Tender, ivory-colored unopened fronds (*kurutholai*) of the palmyra palm are sun-wilted, stripped of thorny midribs (*eerkku*), and dyed in boiling turmeric (*manjal*), sappanwood (*pathimugam*), and lime baths.\n- **Hollow Octahedral & Cubic Lock-Folding**: Using four or six interlocking strips woven at $60^\\circ$ or $90^\\circ$ bias angles, artisans fold a hollow three-dimensional cage, drop dried *kalarchikkai* seeds, tamarind pits, or small terracotta pellets inside before tucking the final locking flap, and plait the trailing stems into a flexible handle that cannot splinter or cut infant gums.\n\n**2. Lathe-Turned Nada-Vandi & Lacquer Finishing (*Kadaisal & Arakku*):**\n- Carpenters turn seasoned *veppamaram* (neem) or *poovarasu* (*Thespesia populnea*) spindles and solid wheels on a bow-lathe (*kadaisal-pattarai*). A triangular A-frame chassis supports one front steerable wheel and two rear axle wheels with a pitched crossbar handle. While spinning on the lathe, sticks of natural insect lac (*arakku*) blended with turmeric and indigo are friction-melted onto the wood and burnished with a screw-pine (*thazhampoo*) leaf to a mirror-gloss, saliva-safe finish."
    },
    {
        "slug": "artifact-siru-ther-miniature-wheeled-carts-and-sanga-kalam-terracotta-figurines",
        "category": "artifact",
        "file": "artifact-siru-ther-miniature-wheeled-carts-and-sanga-kalam-terracotta-figurines.md",
        "name_en": "Siru-Ther Miniature Wheeled Chariots, Terracotta Spoked Wheels & Sangam Excavated Pull-Toys",
        "name_ta": "சிறுதேர் உருளை வண்டிகள், சுடுமண் ஆரச்சக்கரங்கள் மற்றும் சங்ககால அகழாய்வுப் பொம்மைகள்",
        "era": "Iron Age to Early Medieval Era",
        "year_start": -600,
        "year_end": 800,
        "thinai": "marutham",
        "summary_en": "Archaeological corpus of ancient Tamil children's pull-toys and figurines excavated at Keeladi, Korkai, Uraiyur, Karur, and Boluvampatti: perforated terracotta wheels with painted spokes, miniature ram and humped-bullock carts (siru-ther), bird whistles, and pinched mother-and-child figurines.",
        "summary_ta": "கீழடி, கொற்கை, உறையூர், கரூர் மற்றும் போளுவாம்பட்டி அகழாய்வுகளில் கண்டெடுக்கப்பட்ட துளையிட்ட சுடுமண் சக்கரங்கள், சிறுதேர் வண்டிகள், விலங்கு உருவ பொம்மைகள் மற்றும் பறவை ஊதுகுழல்கள்.",
        "sources": [
            "Tamil Nadu State Department of Archaeology Keeladi & Korkai Excavation Reports",
            "Ancient Terracotta Art of Tamil Nadu (S. Gurumurthy)",
            "Uraiyur & Boluvampatti Archaeological Monographs"
        ],
        "content": "# Siru-Ther Miniature Wheeled Carts & Sangam Terracotta Figurines\n\nStratigraphic excavations across Vaigai, Tamiraparani, Noyyal, and Kaveri basin urban sites confirm that the *siru-ther* pull-carts celebrated in Sangam poetry were ubiquitous household artifacts:\n\n**Archaeological Typology:**\n- **Perforated Terracotta Wheels (*urulai*)**: Hundreds of biconvex and flat-rimmed baked clay discs (4 to 9 cm diameter) pierced with a central axle hole have been recovered from Keeladi, Korkai, Alagankulam, and Uraiyur. Many feature prominent central hubs (*kudam*) and radial lines incised or painted in white kaolin to represent wooden wheel spokes (*aaram*).\n- **Zoomorphic Pull-Toys**: Molded terracotta rams, humped *Bos indicus* bulls, elephants, and horses pierced transversely through the legs to accept wooden axles, along with a nostril perforation for tying a cotton pull-string (*kயிறு*).\n- **Avian Rattles & Whistles**: Hollow terracotta peacocks and doves containing baked clay pellets or blow-holes (*oothu-kuzhal*) that produce warbling bird calls when blown by children."
    },
    {
        "slug": "artifact-soppana-saman-miniature-kitchenware-marappachi-couples-and-golu-bommai-sets",
        "category": "artifact",
        "file": "artifact-soppana-saman-miniature-kitchenware-marappachi-couples-and-golu-bommai-sets.md",
        "name_en": "Soppana-Saman Miniature Culinary Play-Sets, Marappachi Couples & Narrative Golu Bommai Ensembles",
        "name_ta": "சொப்புச் சாமான் சமையல் விளையாட்டுக் கருவிகள், மரப்பாச்சி இணையர் மற்றும் கொலு பொம்மைத் தொகுப்புகள்",
        "era": "Early Medieval to Modern Era",
        "year_start": 600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Material typology of domestic Tamil playthings and ritual display dolls: scaled-down soapstone (maavukkal), brass, terracotta, and lac-turned wooden kitchen sets (soppana-saman / soppu-saman), geometric red-sandalwood Marappachi couples dressed by children, and multi-figure terracotta Golu sets.",
        "summary_ta": "மாவுக்கல், பித்தளை, சுடுமண் மற்றும் அரக்கு மரத்தாலான சொப்புச் சாமான்கள் (சிறு அம்மி, ஆட்டுக்கல், உரல், பானை), ஆடை அணிவித்து விளையாடும் மரப்பாச்சிப் பொம்மைகள் மற்றும் நவராத்திரி கொலு பொம்மைத் தொகுப்புகள்.",
        "sources": [
            "Folklore & Material Culture of Tamil Childhood",
            "South Indian Lacquerware & Soapstone Toy Catalogs",
            "Ethnography of Domestic Play in Tamil Nadu"
        ],
        "content": "# Soppana-Saman Miniature Kitchenware, Marappachi Couples & Golu Ensembles\n\nTraditional Tamil domestic play (*siru-veedu* and *kootாஞ்சோறு*) revolves around accurately scaled functional replicas of household tools known collectively as *Soppana-Saman* (or *Soppu-Saman*):\n\n**1. Four-Medium Soppana-Saman Culinary Kits:**\n- **Soapstone (*Maavukkal* / Steatite)**: Hand-carved miniature roller stones (*ammikkal*), wet-grinding mortars (*aatukkal*), grain pounders (*ural-ulakkai*), three-stone hearths (*aduppu*), and rotary *thiruvai* hand-mills capable of actually grinding soaked rice or roasted gram during children's courtyard play.\n- **Terracotta (*Mann-Soppu*) & Brass (*Pithalai-Soppu*)**: Wheel-thrown miniature cooking pots (*pongal-panai*), water pitchers (*kudam*), colanders, and cast-brass ladles (*karandi*), *kuzhi-paniyaram* skillets, and *idli* steamers.\n- **Lac-Turned Wood (*Maram-Soppu*)**: Brightly striped crimson-green-yellow wooden spice boxes (*anjaraipetti*) and churners (*mathu*).\n\n**2. Marappachi & Narrative Golu Sets:**\n- Paired angular *sen-chandana* wood figures with stylized headgear and incised ornaments, alongside painted clay village-marketsets (*kடைத்தெரு* ensembles: grain sellers with miniature measures, weavers, and temple processions)."
    },
    {
        "slug": "institution-bommai-kuyavar-and-pathar-toy-making-artisan-lineages-and-guild-markets",
        "category": "institution",
        "file": "institution-bommai-kuyavar-and-pathar-toy-making-artisan-lineages-and-guild-markets.md",
        "name_en": "Bommai-Kuyavar, Pathar & Thachar Toy-Making Artisan Lineages, Mold Inheritance & Festival Markets",
        "name_ta": "பொம்மைக் குயவர், பத்தர் மற்றும் தச்சர் கைவினைஞர் மரபுகள், தாய்-அச்சு உரிமை மற்றும் திருவிழாச் சந்தைகள்",
        "era": "Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Socio-economic organization of hereditary Tamil toy-making guilds: Bommai-Kuyavar (terracotta and paper-mache molders), Pathar (sculptor-painters), and Marappachi Thachar (wood-turners), intergenerational transmission of master terracotta mother-molds (thai-achu), and seasonal festival market circuits.",
        "summary_ta": "சுடுமண் மற்றும் கூழ் பொம்மைகள் செய்யும் பொம்மைக் குயவர், வண்ணம் தீட்டும் பத்தர் மற்றும் மரப்பாச்சி கடைசல் தச்சர் குடும்பங்களின் பரம்பரைத் தொழில் அமைப்பு, தாய்-அச்சு சொத்துரிமை மற்றும் திருவிழாச் சந்தை வணிகம்.",
        "sources": [
            "Castes and Tribes of Southern India (Thurston)",
            "Cuddalore & Thanjavur District Gazetteers (Handicrafts Chapters)",
            "Artisan Guilds and Temple Fair Economies of Tamil Nadu"
        ],
        "content": "# Bommai-Kuyavar, Pathar & Thachar Toy-Making Artisan Lineages\n\nThe production of terracotta figurines, counterweight dolls, and wooden playthings in Tamil Nadu is sustained by specialized hereditary craft households operating on a seasonal agro-ritual calendar:\n\n**Guild Division of Labor & Workshop Economy:**\n- **Household Specialization**: Within *Bommai-Kuyavar* (potter-sculptor) and *Pathar* / *Raju* artisan families, men traditionally excavate river clay, carve prototype sculptures (*thai-bommai*), and fire the clamp kilns, while women and apprentices press clay and paper-mache sheets into molds, join limb seams, apply tamarind-seed gesso, and paint facial features (*kann-thirathal*).\n- **Mother-Mold Inheritance (*Thai-Achu*)**: Durable baked-clay and plaster negative molds—often comprising 40 to 100 distinct character sets per workshop—are guarded as prime family capital and partitioned as dowry or patrimonial shares across generations.\n- **Festival & Sandhai Circuits**: Artisan guilds align firing schedules with major seasonal gatherings: *Chithirai* and *Vaikasi* temple car festivals (*ther-thiruvizha*), *Adi Perukku* river festivals (where painted clay horses and *manjal* figurines are sold along riverbanks), and the pre-*Purattasi* wholesale fair for *Navaratri Bommai Golu*."
    },
    {
        "slug": "place-panruti-ancient-gadilam-clay-doll-and-terracotta-toy-haven",
        "category": "place",
        "file": "place-panruti-ancient-gadilam-clay-doll-and-terracotta-toy-haven.md",
        "name_en": "Panruti: Ancient Gadilam River Alluvial Clay Doll & Terracotta Toy Craft Haven",
        "name_ta": "பண்ருட்டி - கெடிலம் ஆற்று வண்டல் களிமண் பொம்மை மற்றும் சுடுமண் விளையாட்டுப் பொருட்களின் தாயகத் தளம்",
        "era": "Early Medieval to Modern Era",
        "year_start": 700,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Historic craft town on the northern banks of the Gadilam river in Cuddalore district (lat 11.7740, lng 79.5530), celebrated across South India for its ultra-fine plastic Gadilam alluvial clay deposits and hereditary Bommai-Kuyavar artisan quarters producing terracotta pull-toys, Thalaiyatti bobbleheads, and Navaratri Golu dolls.",
        "summary_ta": "கடலூர் மாவட்டத்தில் கெடிலம் ஆற்றங்கரையில் அமைந்துள்ள பண்ருட்டி (lat 11.7740, lng 79.5530): மென்மையான வண்டல் களிமண் வளமும், சுடுமண் சிறுதேர், தலையாட்டி மற்றும் கொலு பொம்மைகள் செய்யும் கைவினைஞர் வீதிகளும் நிறைந்த வரலாற்றுத் தளம்.",
        "sources": [
            "South Arcot / Cuddalore District Gazetteer",
            "Geographical Indication Registry Reports on Tamil Nadu Clay Toys",
            "Gadilam River Basin Cultural Geography"
        ],
        "content": "# Panruti: Ancient Gadilam River Alluvial Clay Doll & Terracotta Toy Haven\n\nSituated at `lat 11.7740, lng 79.5530` on the fertile *Marutham* plains of the Gadilam river in Cuddalore district (historic *Nadunadu* / *Thiruvathigai* hinterland), Panruti is one of Tamil Nadu's foremost historical centers for terracotta and composite doll manufacture:\n\n**Geological & Craft Significance:**\n- **Gadilam Alluvial Clay (*Gadilam Vandal*)**: Seasonal floods of the Gadilam river deposit deep beds of fine-grained, micaceous, secondary illite-kaolinite clay with exceptional wet plasticity and low grit content. Unlike coarse brick earths, Panruti clay captures hair-thin facial incisions inside press-molds without cracking during sun-drying or low-temperature kiln firing (~650–750°C).\n- **Artisan Streets & Workshop Clusters**: Quarters in Panruti, Thiruvathigai, and neighboring Vandipalayam house dozens of hereditary *Bommai-Kuyavar* and *Pathar* families who produce thousands of *Thalaiyatti* counterweight dolls, wheeled terracotta animals, *soppana-saman* clay sets, and multi-tiered *Navaratri Golu* ensembles shipped to temple towns across Tamil Nadu."
    }
]

EDGES = [
    [
        "text-sangam-and-bhakti-literature-on-siru-ther-toy-carts-and-childhood-playthings",
        "describes",
        "artifact-siru-ther-miniature-wheeled-carts-and-sanga-kalam-terracotta-figurines",
        "material_culture",
        "Sangam to Medieval Era",
        "Kalittokai, Akananuru, and Periazhwar Tirumozhi celebrate toddlers rolling miniature siru-ther wheeled carts across courtyard sands.",
        "Kalittokai & Akananuru"
    ],
    [
        "text-sangam-and-bhakti-literature-on-siru-ther-toy-carts-and-childhood-playthings",
        "codifies",
        "concept-pillai-tamizh-developmental-stages-and-kinesthetic-childhood-toy-pedagogy",
        "material_culture",
        "Sangam to Modern Era",
        "Pillai-Tamizh poetic grammar structures early childhood into ten developmental milestones paired with rattles, dolls, and toy carts.",
        "Periazhwar Tirumozhi"
    ],
    [
        "concept-pillai-tamizh-developmental-stages-and-kinesthetic-childhood-toy-pedagogy",
        "guides_design_of",
        "technology-palmyra-leaf-olai-kilukiluppai-braiding-and-wooden-nada-vandi-joinery",
        "material_culture",
        "Sangam to Modern Era",
        "Developmental stages of auditory tracking and bipedal gait training govern the design of braided olai-kilukiluppai rattles and three-wheeled nada-vandi walkers.",
        "Panniru Pattiyal"
    ],
    [
        "concept-sen-chandana-marappachi-medicinal-teething-dolls-and-navaratri-golu-pedagogy",
        "informs",
        "artifact-soppana-saman-miniature-kitchenware-marappachi-couples-and-golu-bommai-sets",
        "material_culture",
        "Early Medieval to Modern Era",
        "Medicinal red-sandalwood teething traditions and Navaratri Golu cosmological tiers shape the crafting of Marappachi couples and Golu figurine sets.",
        "Folk Toys of Tamil Nadu"
    ],
    [
        "concept-thalaiyatti-bommai-weighted-hemisphere-center-of-mass-and-gimbal-oscillation",
        "underpins",
        "technology-gadilam-alluvial-clay-press-molding-and-tapioca-paper-mache-shell-casting",
        "material_culture",
        "Medieval to Modern Era",
        "Self-righting center-of-mass physics requires pairing heavy press-molded alluvial clay bases with ultra-lightweight tapioca-paper-mache upper shells.",
        "Thanjavur & Panruti Craft Manuals"
    ],
    [
        "technology-gadilam-alluvial-clay-press-molding-and-tapioca-paper-mache-shell-casting",
        "produces",
        "artifact-soppana-saman-miniature-kitchenware-marappachi-couples-and-golu-bommai-sets",
        "material_culture",
        "Early Medieval to Modern Era",
        "Two-piece terracotta press-molding and composite paper-mache casting produce the narrative Golu Bommai ensembles and clay soppana-saman sets.",
        "Handicrafts of Tamil Nadu Survey"
    ],
    [
        "technology-palmyra-leaf-olai-kilukiluppai-braiding-and-wooden-nada-vandi-joinery",
        "fabricates",
        "artifact-siru-ther-miniature-wheeled-carts-and-sanga-kalam-terracotta-figurines",
        "material_culture",
        "Sangam to Modern Era",
        "Traditional lathe-turning and axle joinery techniques produce the wheeled siru-ther pull-chariots and toddler walkers.",
        "Traditional Wood Turning Studies"
    ],
    [
        "institution-bommai-kuyavar-and-pathar-toy-making-artisan-lineages-and-guild-markets",
        "practices",
        "technology-gadilam-alluvial-clay-press-molding-and-tapioca-paper-mache-shell-casting",
        "material_culture",
        "Medieval to Modern Era",
        "Hereditary Bommai-Kuyavar and Pathar artisan families preserve master mother-molds (thai-achu) and mineral painting techniques across generations.",
        "Cuddalore District Gazetteer"
    ],
    [
        "institution-bommai-kuyavar-and-pathar-toy-making-artisan-lineages-and-guild-markets",
        "flourishes_in",
        "place-panruti-ancient-gadilam-clay-doll-and-terracotta-toy-haven",
        "material_culture",
        "Early Medieval to Modern Era",
        "Bommai-Kuyavar artisan lineages cluster in Panruti along the Gadilam river to harvest its plastic alluvial clay for year-round toy production.",
        "South Arcot District Gazetteer"
    ],
    [
        "place-panruti-ancient-gadilam-clay-doll-and-terracotta-toy-haven",
        "supplies",
        "artifact-soppana-saman-miniature-kitchenware-marappachi-couples-and-golu-bommai-sets",
        "material_culture",
        "Early Medieval to Modern Era",
        "Panruti workshops supply terracotta Golu Bommai sets, counterweight dolls, and miniature clay vessels to households and temple fairs across Tamil Nadu.",
        "GI Registry Reports"
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
