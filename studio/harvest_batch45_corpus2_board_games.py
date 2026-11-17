#!/usr/bin/env python3
"""
Harvester: Batch 45 - Ancient Tamil Traditional Board Games, Strategy Geometry, Temple Flagstone Diagrams & Dice Craft
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
        "slug": "text-tirukkural-koodhu-and-sangam-literature-on-kavar-dice-and-gaming-halls",
        "category": "text",
        "file": "text-tirukkural-koodhu-and-sangam-literature-on-kavar-dice-and-gaming-halls.md",
        "name_en": "Tirukkural Koodhu Chapter & Sangam References to Kavar Dice and Kazhagam Gaming Halls",
        "name_ta": "திருக்குறள் சூது அதிகாரம் மற்றும் சங்க இலக்கியக் கவர் பகடை, கழக ஆடுகளக் குறிப்புகள்",
        "era": "Sangam to Post-Sangam Era",
        "year_start": -300,
        "year_end": 500,
        "thinai": "marutham",
        "summary_en": "Classical Tamil literary references in Tirukkural (Chapter 94, Soodhu / Koodhu), Kalittokai, and Narrinai examining the terminology of dice (kavar, aya, kalagam), public gaming arenas, and the distinction between recreational domestic board games and wagering.",
        "summary_ta": "திருக்குறளின் சூது அதிகாரம், கலித்தொகை மற்றும் நற்றிணையில் குறிப்பிடப்படும் கவர் பகடைக் காய்கள், கழகம் எனப்படும் ஆடுகளங்கள் மற்றும் மனக்கணக்கு சார்ந்த பலகை விளையாட்டு மரபு.",
        "sources": [
            "Tirukkural (Adhigaram 94: Soodhu)",
            "Kalittokai",
            "Narrinai",
            "Traditional Games of Tamil Nadu Ethnographic Studies"
        ],
        "content": "# Tirukkural & Sangam Literature on Kavar Dice and Gaming\n\nClassical Tamil literature preserves a specialized vocabulary for dice, board lattices, and public gaming spaces:\n\n**Literary & Lexical Testimony:**\n- **Tirukkural (*Soodhu* / Chapter 94)**: Valluvar devotes ten couplets to analyzing the psychology of wagering with tumbling dice (*kavar*) in public gaming halls (*kazhagam*), contrasting destructive gambling with disciplined statecraft while recording technical terms for casting lots and board tallies.\n- **Sangam Poetic References**: Poems in *Kalittokai* and *Narrinai* refer to ivory and bone dice (*kavar-kayi*) cast across lined boards by urban elders resting in shaded village *manrams*, as well as young girls playing seed-counting games (*kazhangu* / *ammanai*) with polished *kalarchikkai* (*Caesalpinia bonduc*) nuts on sandy courtyards."
    },
    {
        "slug": "concept-pallanguzhi-mancala-sowing-combinatorics-and-mental-modulo-arithmetic",
        "category": "concept",
        "file": "concept-pallanguzhi-mancala-sowing-combinatorics-and-mental-modulo-arithmetic.md",
        "name_en": "Pallanguzhi Mancala Sowing Combinatorics, Karuvu Capture Rules & Modulo-14 Arithmetic",
        "name_ta": "பல்லாங்குழி விதைப்புச் சேர்க்கைக் கணிதம், கருவு எடுத்தல் விதிகள் மற்றும் 14-குழி சுழல் மனக்கணக்கு",
        "era": "Early Medieval to Modern Era",
        "year_start": 500,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Mathematical structure of the Tamil two-row 14-cup mancala board game (Pallanguzhi): relay sowing mechanics (thodakku), empty-pit capture (thudaippu), accumulation of four-seed sets (pasu), and rapid mental modulo-14 residue calculation.",
        "summary_ta": "பல்லாங்குழி ஆட்டத்தின் கணிதக் கட்டமைப்பு: ஏழு-ஏழு குழிகளில் சோழிகள் அல்லது புளியங்கொட்டைகளை இட்டுத் தொடர் விதைப்பு செய்தல், துடைப்பு மற்றும் பசு எடுத்தல் மூலம் பயிற்றுவிக்கப்படும் மனக்கணக்கு.",
        "sources": [
            " Ethnographic Atlas of Traditional Tamil Board Games",
            "History of Board Games in India (Finkel / Bock-Raming)",
            "Kreeda Traditional Games Archive"
        ],
        "content": "# Pallanguzhi Sowing Combinatorics & Modulo-14 Arithmetic\n\n*Pallanguzhi* (*Pannirandu-Kuzhi* / *Pathinangu-Kuzhi*) is the classical Tamil member of the mancala family of count-and-capture games, played on a board of two parallel rows of seven hemispherical cups:\n\n**Combinatorial Mechanics:**\n- **Initial Distribution & Relay Sowing**: Typically initialized with 5, 6, or 12 counters (tamarind seeds, cowrie shells, or red *kundrimani* seeds) per cup (70, 84, or 168 total). A player lifts all seeds from one cup and distributes them one-by-one counter-clockwise, picking up the contents of the next cup after the last seed lands to continue a multi-lap relay.\n- **Thudaippu & Pasu Captures**: If the final seed of a lap lands before an empty cup (*verum-kuzhi*), the player captures all seeds in the cup beyond it (*thudaippu*) together with the opposite cup's contents. Whenever any cup accumulates exactly four seeds (*pasu*), those four are immediately claimed by that row's owner.\n- **Cognitive Pedagogy**: Experienced players mentally compute $n \\pmod{14}$ across multi-lap cascades before lifting a cup."
    },
    {
        "slug": "concept-aadu-puli-aattam-asymmetric-graph-blockade-and-predator-prey-topology",
        "category": "concept",
        "file": "concept-aadu-puli-aattam-asymmetric-graph-blockade-and-predator-prey-topology.md",
        "name_en": "Aadu-Puli-Aattam Asymmetric Graph Topology, Vertex Degree Connectivity & Blockade Strategy",
        "name_ta": "ஆடு புலி ஆட்டம் சமச்சீரற்ற வலைப்பின்னல் வடிவவியல், முனை இணைப்பு மற்றும் முற்றுகை உத்தி",
        "era": "Early Medieval to Modern Era",
        "year_start": 500,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Graph-theoretic geometry of the Tamil tiger-and-goat hunt game (Aadu-Puli-Aattam): a 23-vertex planar graph formed by a central apex triangle intersected by four horizontal lines, where 3 leaping tigers compete against 15 drop-and-slide goats aiming to reduce tiger mobility to zero.",
        "summary_ta": "ஆடு புலி ஆட்டத்தின் வடிவவியல் மற்றும் வலைப்பின்னல் உத்தி: 23 சந்திப்புப் புள்ளிகள் கொண்ட முக்கோணக் கட்டத்தில் 3 புலிகளும் 15 ஆடுகளும் மோதும் சமச்சீரற்ற முற்றுகை விளையாட்டு.",
        "sources": [
            "Graph Theory of Traditional Indian Hunt Games",
            "Temple Floor Game Diagrams of Tamil Nadu",
            "Kreeda Traditional Games Research"
        ],
        "content": "# Aadu-Puli-Aattam Asymmetric Graph Topology\n\n*Aadu-Puli-Aattam* (Goat and Tiger Game) is a zero-sum, perfect-information asymmetric blockade game played on a distinctive triangular planar graph:\n\n**Graph Geometry & Strategic Equilibrium:**\n- **The 23-Vertex Lattice**: Four rays diverge from a single top apex vertex (*उச்சி*) down to a base line, crossed by three horizontal segments that extend outward into side wings, creating 23 intersection vertices of varying degree (degree 2 at corners, degree 4 at interior crossings, degree 4 at the apex).\n- **Phase 1 (Placement) vs Phase 2 (Movement)**: The three tigers start on the apex and inner vertices and can capture any adjacent goat by leaping over it along a straight line into an immediately vacant vertex. The 15 goats enter the board one per turn and cannot move until all 15 are placed.\n- **Invariant Defense**: Goats win by forming double-layered walls along outer degree-2 and degree-3 edges where tigers cannot jump over them, progressively shrinking the tigers' reachable subgraph until all three tigers have zero legal moves."
    },
    {
        "slug": "technology-temple-mandapa-flagstone-game-board-incising-and-mason-layout",
        "category": "technology",
        "file": "technology-temple-mandapa-flagstone-game-board-incising-and-mason-layout.md",
        "name_en": "Temple Mandapa Granite Flagstone Game-Board Incising, Cup-Pecking & Mason Geometry",
        "name_ta": "கோயில் மண்டபக் கற்தளங்களில் விளையாட்டுக் கட்டங்கள் செதுக்குதல் மற்றும் குழி கொத்துதல் நுட்பம்",
        "era": "Pallava to Vijayanagara-Nayak Era",
        "year_start": 600,
        "year_end": 1700,
        "thinai": "marutham",
        "summary_en": "Lithic craft and archaeological distribution of permanent board-game diagrams pecked and chiselled into granite flagstones across Tamil temple mandapas, gopura thresholds, and river bathing ghats: straight-edge scoring, compass arcs, and hemispherical cup-grinding.",
        "summary_ta": "பல்லவர், சோழர், பாண்டியர் மற்றும் நாயக்கர் காலக் கோயில் மண்டபக் கற்தளங்களிலும் படித்துறைகளிலும் உளி கொண்டு நிரந்தரமாகச் செதுக்கப்பட்ட பல்லாங்குழி, ஆடுபுலி மற்றும் தாயக் கட்டங்களின் தொழில்நுட்பம்.",
        "sources": [
            "ludic Graffito in South Indian Temples Surveys",
            "Archaeological Survey of India Epigraphical & Architectural Notes",
            "Thanjavur & Madurai Temple Pavement Studies"
        ],
        "content": "# Temple Mandapa Flagstone Game-Board Incising\n\nHundreds of historic Tamil temples—from Mamallapuram, Thanjavur, and Darasuram to Srirangam, Madurai, and Rameswaram—preserve board-game diagrams carved directly into their granite floor slabs:\n\n**Lithic Engraving Techniques:**\n1. **Chisel Scoring & Compass Layout**: Masons and temple servants used pointed iron punches (*koor-uli*) and straight-edges to score permanent shallow V-grooves ($2-4\\text{ mm}$ deep) for *Aadu-Puli-Aattam* triangles, *Thaayam* concentric squares, and three-in-a-row *Kodu-Aattam* (Nine Men's Morris) grids on shaded verandah benches (*thinnai*).\n2. **Cup Pecking & Abrasive Grinding**: Stone *Pallanguzhi* boards were formed by pecking two rows of seven cavities into thick granite slabs and grinding the interiors smooth with rounded quartz river cobbles and wet sand so seeds could be scooped cleanly without catching fingertips."
    },
    {
        "slug": "technology-chettinad-wood-turning-hinged-pallanguzhi-carving-and-brass-thaayak-kattai",
        "category": "technology",
        "file": "technology-chettinad-wood-turning-hinged-pallanguzhi-carving-and-brass-thaayak-kattai.md",
        "name_en": "Hinged Teakwood Pallanguzhi Carving, Lathe-Turned Legs & Brass Thaayak-Kattai Dice Casting",
        "name_ta": "மடக்குத் தேக்குமரப் பல்லாங்குழி செதுக்குதல், கடைசல் கால்கள் மற்றும் பித்தளைத் தாயக்கட்டை வார்ப்பு",
        "era": "Medieval to Modern Era",
        "year_start": 1400,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Cabinetry and metalworking techniques for domestic Tamil gaming sets: hollowing matched teak or rosewood blocks into fish- and boat-shaped folding Pallanguzhi boxes with brass hinges, lac-turning stand legs, and casting balanced four-sided brass or ivory stick dice (thaayak-kattai).",
        "summary_ta": "செட்டிநாடு மற்றும் தஞ்சாவூர் மர வேலைப்பாட்டில் உருவான மீன் வடிவ மடக்குப் பல்லாங்குழிப் பெட்டிகள், அரக்கு பூசிய கடைசல் கால்கள் மற்றும் பித்தளை, தந்தத் தாயக்கட்டைகள் தயாரிக்கும் நுட்பம்.",
        "sources": [
            "Chettinad Woodcarving & Domestic Arts Monographs",
            "Madras Museum Ethnographic Collection",
            "Handicrafts of Tamil Nadu Gazetteer"
        ],
        "content": "# Hinged Pallanguzhi Woodcarving & Brass Dice Casting\n\nIn domestic Tamil households—especially across Chettinad and the Kaveri delta—gaming boards were crafted as heirloom furniture and bridal trousseau (*seer-varisai*) pieces:\n\n**Craft & Fabrication Sequence:**\n1. **Matched Twin-Leaf Gouging**: Carpenters split a single seasoned block of Burmese or Malabar teak (*Tectona grandis*) or jackwood into two book-matched leaves, gouging seven smooth hemispherical cups into each leaf so the box folded shut like aclam shell to hold seeds inside.\n2. **Zoomorphic & Lac-Turned Profiles**: Outer shells were shaped into stylized fish (*meen-pallanguzhi*), peacocks, or temple boats, mounted on lathe-turned legs coated with colored shellac (*arakku*).\n3. **Balanced Stick Dice (*Thaayak-Kattai*)**: Metalworkers cast pairs of elongated square-prism brass rods (or carved bone/ivory prisms) and drilled 1, 2, and 3 pip-dots on three long faces while leaving the fourth face blank, grinding all four faces to equal weight so roll probabilities remained unbiased."
    },
    {
        "slug": "artifact-thaayak-kattai-stick-dice-cowrie-lots-and-folding-pallanguzhi-chests",
        "category": "artifact",
        "file": "artifact-thaayak-kattai-stick-dice-cowrie-lots-and-folding-pallanguzhi-chests.md",
        "name_en": "Thaayak-Kattai Prism Dice, Slit Cowrie Lots (achiram) & Folding Pallanguzhi Chests",
        "name_ta": "தாயக்கட்டை நீள்சதுரப் பகடைகள், சோழிப் பகடைகள் மற்றும் மடக்குப் பல்லாங்குழிப் பெட்டிகள்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Material artifact assemblage of Tamil board games: bone, ivory, and brass four-sided stick dice (thaayak-kattai / kavar), six-or-four cowrie shell lots (sozhi), Abrus precatorius (kundrimani) and tamarind seed counters, and carved folding Pallanguzhi boxes.",
        "summary_ta": "தமிழர் பலகை விளையாட்டுப் பொருட்கள்: தந்தம், எலும்பு மற்றும் பித்தளையால் ஆன நான்கு பட்டைத் தாயக்கட்டைகள், உருட்டும் சோழிகள், குன்றிமணி மற்றும் புளியங்கொட்டைக் காய்கள், மடக்குப் பல்லாங்குழிப் பெட்டிகள்.",
        "sources": [
            "Keezhadi & Kodumanal Bone Artifact Reports",
            "Government Museum Chennai Ethnology Gallery",
            "Dakshinachitra Material Culture Collection"
        ],
        "content": "# Thaayak-Kattai Stick Dice, Cowrie Lots & Pallanguzhi Chests\n\nThe physical gaming kit of Tamil Nadu combines archaeological bone/stone pieces with enduring domestic craft objects:\n\n**Artifact Typology:**\n- **Four-Sided Stick Dice (*Thaayak-Kattai / Kavar*)**: Unlike cubic six-sided dice, traditional Tamil race games use a pair of oblong four-sided prisms ($5-8\\text{ cm}$ long) rolled by rubbing between the palms and dropping onto the floor. Pip markings (0, 1, 2, 3 on each rod) combine to yield outcomes of 1 (*thaayam*), 2, 3, 4, 5, 6, and 12 (*pannerandu*, when both blank faces land up).\n- **Cowrie Shell Lots (*Sozhi*)**: Sets of 4, 6, or 12 *Monetaria moneta* marine cowrie shells cast to binary mouth-up / mouth-down probabilities in *Parama-Padham* and four-player *Thaayam*.\n- **Natural Seed Counters**: Glossy black-and-scarlet *Kundrimani* (*Abrus precatorius*), roasted tamarind seeds (*puliyankottai*), and grey *Kalarchikkai* nuts."
    },
    {
        "slug": "concept-thaayam-cross-and-circle-race-kinematics-and-stick-dice-probability",
        "category": "concept",
        "file": "concept-thaayam-cross-and-circle-race-kinematics-and-stick-dice-probability.md",
        "name_en": "Thaayam Cross-and-Circle Race Topology, Safe-House Symmetry & Stick-Dice Probability",
        "name_ta": "தாயம் சதுர-சுற்றுப் பாதை வடிவவியல், மலைப் பாதுகாப்புக் கட்டங்கள் மற்றும் தாயக்கட்டை நிகழ்தகவு",
        "era": "Early Medieval to Modern Era",
        "year_start": 500,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Probability theory and spatial topology of Tamil Thaayam (Ettu-Kodu / Nanku-Kattai): concentric spiral track navigation from outer perimeter to central home (pazham), cross-hatched safe squares (malai), single-capture vs stacked-blockade rules, and the 16-state probability space of twin four-sided stick dice.",
        "summary_ta": "தாயக் கட்டத்தின் நிகழ்தகவு மற்றும் பாதை அமைப்பு: வெளிச் சுற்றிலிருந்து உள் சுற்று வழியாகப் பழம் சேரும் சுழல் பாதை, வெட்ட முடியாத மலைக் கட்டங்கள் மற்றும் இரு தாயக்கட்டைகளின் 16 நிகழ்தகவு நிலைகள்.",
        "sources": [
            "Probability Analysis of Traditional Indian Race Games",
            "Traditional Games of Tamil Nadu",
            "South Asian Cross-and-Circle Game Studies"
        ],
        "content": "# Thaayam Race Topology & Stick-Dice Probability\n\n*Thaayam* (played on either a four-arm cross lattice or a $5\\times 5$ / $7\\times 7$ concentric square spiral) combines discrete probability distributions with tactical pawn positioning:\n\n**Probability & Spatial Rules:**\n- **16-State Dice Distribution**: Rolling two independent four-sided stick dice (*thaayak-kattai*, each face equally likely with values $\\{0,1,2,3\\}$) generates $4 \\times 4 = 16$ equiprobable states. Special bonus throws—*Thaayam* ($1+0$, probability $2/16$), five ($2+3$, probability $2/16$), six ($3+3$, probability $1/16$), and twelve ($0+0$, probability $1/16$)—grant an immediate extra roll, allowing long chains of accumulated throws before moving pawns.\n- **Spiral Track & Malai Sanctuaries**: Pawns must roll a *Thaayam* (1) to enter the board, circuit the outer perimeter counter-clockwise, and step into the inner ring (*ul-suttru*) toward the central home (*pazham*), contesting cross-marked safe squares (*malai*) and cutting (*vettu*) lone opposing pawns."
    },
    {
        "slug": "institution-thinnai-manram-gaming-circles-and-chettinad-seer-varisai-traditions",
        "category": "institution",
        "file": "institution-thinnai-manram-gaming-circles-and-chettinad-seer-varisai-traditions.md",
        "name_en": "Thinnai-Manram Intergenerational Gaming Circles & Bridal Seer-Varisai Trousseau Custom",
        "name_ta": "திண்ணை-மன்ற விளையாட்டுக் குழுக்களும் செட்டிநாட்டுச் சீர்வரிசைப் பல்லாங்குழி மரபும்",
        "era": "Medieval to Modern Era",
        "year_start": 1000,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Social institutions that sustained traditional Tamil board games: street-facing verandah (thinnai) and village banyan-platform (manram) gaming circles for strategic play, and the custom of gifting silver, brass, or carved teak Pallanguzhi boards in bridal trousseaus (seer-varisai) to foster household numeracy and social bonding.",
        "summary_ta": "பாரம்பரிய விளையாட்டுகளைப் பேணிய சமூக நிறுவனங்கள்: ஊர் மன்றம் மற்றும் வீட்டுத் திண்ணைகளில் முதியோரும் இளையோரும் கூடிய ஆட்டக் குழுக்கள், திருமணச் சீர்வரிசையில் பல்லாங்குழி வழங்கும் மரபு.",
        "sources": [
            "Social History of Chettinad Households",
            "Folklore and Domestic Life in Tamil Nadu",
            "Kreeda Ethnographic Field Notes"
        ],
        "content": "# Thinnai-Manram Gaming Circles & Bridal Trousseau Custom\n\nTraditional board games in Tamil society functioned as informal academies of mental arithmetic, risk assessment, and kinship socialization:\n\n**Social Transmission:**\n- **The Thinnai & Manram Commons**: Every traditional Tamil house featured a raised street verandah (*thinnai*), often with an *Aadu-Puli-Aattam* or *Thaayam* grid permanently scored into the lime plaster or stone slab, where elders and children played during midday heat.\n- **Bridal Seer-Varisai Custom**: Across Chettinad (Nagarathar) and Kaveri delta families, a bride's wedding trousseau (*seer-varisai*) obligatorily included a carved teak, brass, or silver-inlaid *Pallanguzhi* box filled with cowries or red *kundrimani* seeds—both as an emblem of domestic abundance and as a social icebreaker for the new bride in her marital joint family."
    },
    {
        "slug": "place-karaikudi-ancient-chettinad-pallanguzhi-and-gaming-craft-haven",
        "category": "place",
        "file": "place-karaikudi-ancient-chettinad-pallanguzhi-and-gaming-craft-haven.md",
        "name_en": "Karaikudi: Chettinad Pallanguzhi Woodcarving, Brass Dice Craft & Thinnai Gaming Haven",
        "name_ta": "காரைக்குடி - செட்டிநாட்டுப் பல்லாங்குழி மரவேலைப்பாடு, பித்தளைத் தாயக்கட்டை மற்றும் திண்ணை ஆட்டத் தளம்",
        "era": "Medieval to Modern Era",
        "year_start": 1500,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Principal heritage town of the Chettinad region in Sivaganga district, celebrated for its palatial courtyards (valavu), master woodcarvers and brass founders crafting heirloom fish-shaped Pallanguzhi chests and stick dice, and living household board-game traditions.",
        "summary_ta": "சிவகங்கை மாவட்டத்தில் அமைந்துள்ள செட்டிநாட்டின் மைய நகரமான காரைக்குடி: வளவு வீடுகளின் திண்ணை ஆட்டக் களங்கள், கலைநயமிக்க தேக்குமரப் பல்லாங்குழிப் பெட்டிகள் மற்றும் பித்தளைத் தாயக்கட்டைத் தயாரிப்பின் தாயகம்.",
        "sources": [
            "Sivaganga District Gazetteer",
            "Chettinad Heritage & Material Culture Survey",
            "Handicrafts Directory of Tamil Nadu"
        ],
        "content": "# Karaikudi: Chettinad Pallanguzhi & Gaming Craft Haven\n\nKaraikudi and its surrounding Nagarathar settlements in Sivaganga district represent the foremost center for the preservation and artisanal manufacture of traditional Tamil board-game equipment:\n\n**Artisanal & Architectural Context:**\n- **Valavu Courtyard Culture**: The expansive central courtyards (*valavu*) and cool granite-flagged verandahs of Karaikudi mansions served as daily gathering spaces where women and elders played multi-round *Pallanguzhi* and *Thaayam* tournaments during festival seasons.\n- **Wood & Brass Guilds**: Local woodcarvers (working in seasoned Burma teak salvaged and imported through Nagarathar maritime networks) and brass smiths in Karaikudi and nearby Kottaiyur specialized in lathe-turned, lacquered *Pallanguzhi* chests, miniature silver seed-cups, and precision-weighted brass *thaayak-kattai* dice."
    },
    {
        "slug": "artifact-engraved-steatite-and-terracotta-gaming-counters-and-kalarchikkai-seeds",
        "category": "artifact",
        "file": "artifact-engraved-steatite-and-terracotta-gaming-counters-and-kalarchikkai-seeds.md",
        "name_en": "Terracotta Hopscotch Discs (sillu), Bone Gaming Pawns & KalarchikkaiTossing Nuts",
        "name_ta": "சுடுமண் சில்லு வட்டுகள், எலும்பு ஆட்டக் காய்கள் மற்றும் கழற்சிக்காய்-குன்றிமணி எண்ணிக்கைக் காய்கள்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Archaeological and botanical gaming tokens of Tamil Nadu: ground potsherd discs (sillu / pandi) and conical terracotta/bone game pawns excavated at Sangam urban sites (Keezhadi, Alagankulam, Kodumanal), alongside hard grey Caesalpinia bonduc (kalarchikkai) nuts used in seven-stone kazhangu dexterity games.",
        "summary_ta": "கீழடி, கொடுமணல் உள்ளிட்ட அகழ்வாய்வுகளில் கண்டெடுக்கப்பட்ட வட்ட வடிவ சுடுமண் சில்லுகள், கூம்பு வடிவ ஆட்டக் காய்கள் மற்றும் கழங்கு ஆடப் பயன்படும் கழற்சிக்காய்கள்.",
        "sources": [
            "Keezhadi Archaeological Excavation Reports (TNSDA)",
            "Alagankulam & Uraiyur Terracotta Finds",
            "Sangam Games and Pastimes Studies"
        ],
        "content": "# Terracotta Sillu Discs, Bone Pawns & Kalarchikkai Nuts\n\nExcavations across Early Historic Tamil settlements have recovered hundreds of purpose-made gaming tokens that bridge archaeological strata with living village games:\n\n**Token Categories:**\n- **Ground Potsherd Discs (*Sillu*)**: Circular discs ($3-6\\text{ cm}$ diameter) chipped and edge-ground from broken Black-and-Red Ware or Russet-Coated potsherds, used as pitching discs in grid-hopping games (*Pandi / Nondi*) and as flat board counters.\n- **Conical Terracotta & Bone Pawns**: Miniature turned cones and cylinder tokens with incised collars recovered at Keezhadi and Uraiyur, corresponding to race-game pawns (*kayi*).\n- **Botanical Counters (*Kalarchikkai & Kundrimani*)**: Smooth, stony grey seeds of the fever-nut vine (*Caesalpinia bonduc*, *kalarchikkai*) tossed and caught in rhythmic *Kazhangu* (*Kallangai*) dexterity sets, alongside uniform crimson-and-black *Abrus precatorius* seeds."
    }
]

EDGES = [
    [
        "text-tirukkural-koodhu-and-sangam-literature-on-kavar-dice-and-gaming-halls",
        "documents",
        "artifact-thaayak-kattai-stick-dice-cowrie-lots-and-folding-pallanguzhi-chests",
        "material_culture",
        "Sangam to Post-Sangam Era",
        "Tirukkural and Sangam verses attest to the ancient use of kavar stick dice and cowrie lots in Tamil gaming.",
        "Tirukkural Adhigaram 94"
    ],
    [
        "concept-pallanguzhi-mancala-sowing-combinatorics-and-mental-modulo-arithmetic",
        "governs",
        "technology-chettinad-wood-turning-hinged-pallanguzhi-carving-and-brass-thaayak-kattai",
        "material_culture",
        "Early Medieval to Modern Era",
        "The 14-cup relay sowing rules dictate the twin-row seven-cup geometry of carved Pallanguzhi chests.",
        "Ethnographic Atlas of Games"
    ],
    [
        "concept-aadu-puli-aattam-asymmetric-graph-blockade-and-predator-prey-topology",
        "guides",
        "technology-temple-mandapa-flagstone-game-board-incising-and-mason-layout",
        "material_culture",
        "Pallava to Vijayanagara-Nayak Era",
        "The 23-vertex triangular blockade lattice of Aadu-Puli-Aattam was chiselled into temple mandapa flagstones across Tamil Nadu.",
        "Temple Floor Game Surveys"
    ],
    [
        "technology-chettinad-wood-turning-hinged-pallanguzhi-carving-and-brass-thaayak-kattai",
        "fabricates",
        "artifact-thaayak-kattai-stick-dice-cowrie-lots-and-folding-pallanguzhi-chests",
        "material_culture",
        "Medieval to Modern Era",
        "Teak woodcarving and brass founding produce hinged Pallanguzhi chests and balanced four-sided stick dice.",
        "Chettinad Monographs"
    ],
    [
        "concept-thaayam-cross-and-circle-race-kinematics-and-stick-dice-probability",
        "utilizes",
        "artifact-thaayak-kattai-stick-dice-cowrie-lots-and-folding-pallanguzhi-chests",
        "material_culture",
        "Early Medieval to Modern Era",
        "Thaayam race boards rely on the 16-state probability distribution of twin four-sided thaayak-kattai stick dice.",
        "Probability Analysis of Race Games"
    ],
    [
        "institution-thinnai-manram-gaming-circles-and-chettinad-seer-varisai-traditions",
        "preserves",
        "concept-pallanguzhi-mancala-sowing-combinatorics-and-mental-modulo-arithmetic",
        "material_culture",
        "Medieval to Modern Era",
        "Verandah gaming circles and bridal seer-varisai gifts transmitted Pallanguzhi rules across generations.",
        "Social History of Chettinad"
    ],
    [
        "institution-thinnai-manram-gaming-circles-and-chettinad-seer-varisai-traditions",
        "flourishes_in",
        "place-karaikudi-ancient-chettinad-pallanguzhi-and-gaming-craft-haven",
        "material_culture",
        "Medieval to Modern Era",
        "Karaikudi valavu courtyards and bridal trousseau guilds anchored the Chettinad gaming craft tradition.",
        "Sivaganga Gazetteer"
    ],
    [
        "place-karaikudi-ancient-chettinad-pallanguzhi-and-gaming-craft-haven",
        "hosts",
        "technology-chettinad-wood-turning-hinged-pallanguzhi-carving-and-brass-thaayak-kattai",
        "material_culture",
        "Medieval to Modern Era",
        "Karaikudi woodcarvers and brass smiths specialized in heirloom Pallanguzhi boxes and precision stick dice.",
        "Handicrafts of Tamil Nadu"
    ],
    [
        "technology-temple-mandapa-flagstone-game-board-incising-and-mason-layout",
        "pairs_with",
        "artifact-engraved-steatite-and-terracotta-gaming-counters-and-kalarchikkai-seeds",
        "material_culture",
        "Iron Age to Modern Era",
        "Incised stone floor boards were played using ground potsherd sillu discs, conical pawns, and natural seed counters.",
        "Keezhadi Excavation Reports"
    ],
    [
        "text-tirukkural-koodhu-and-sangam-literature-on-kavar-dice-and-gaming-halls",
        "informs",
        "institution-thinnai-manram-gaming-circles-and-chettinad-seer-varisai-traditions",
        "material_culture",
        "Sangam to Modern Era",
        "Classical ethical and poetic reflections shaped the social distinction between wagering halls and domestic strategy games.",
        "Tirukkural"
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
