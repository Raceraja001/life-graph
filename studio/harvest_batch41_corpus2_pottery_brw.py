#!/usr/bin/env python3
"""
Harvester: Batch 41 - Ancient Tamil Megalithic Black-and-Red Ware (BRW) Pyrotechnics & Urn Burials
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
        "slug": "text-purananuru-verses-addressing-the-potter-kalam-sey-kooce",
        "category": "text",
        "file": "text-purananuru-verses-addressing-the-potter-kalam-sey-kooce.md",
        "name_en": "Purananuru Verses Addressing the Potter Kalam-Sey-Kooce on Giant Burial Urns",
        "name_ta": "கலம்செய்கோவே எனத் தொடங்கும் புறநானூற்று ஈமத்தாழி மண்பாண்டப் பாடல் குறிப்புகள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Purananuru poems (Verses 228, 256) where poets plead with the village master potter ('Kalam-Sey-Kooce') to fashion a burial urn ('Mudhumakkal Thaazhi') large enough to hold the deceased hero along with his vast fame and earth.",
        "summary_ta": "மன்னன் மற்றும் வீரர்களின் மறைவின் போது பூமி அளவிலான பெரும் ஈமத்தாழி வனையும்படி குயவரை விளித்துப் பாடிய புறநானூற்றுப் பாடல்கள் (228, 256).",
        "sources": [
            "Purananuru 228",
            "Purananuru 256",
            "Sangam Ceramic Literary Studies"
        ],
        "content": "# Purananuru Verses Addressing Kalam-Sey-Kooce\n\nThe Sangam anthology *Purananuru* contains poignant elegies directly apostrophizing the ceramic artisan as *Kalam-Sey-Kooce* (the master potter who makes vessels):\n\n**Poetic Excerpts:**\n- **Purananuru 228 (by Aiyur Mudavanar)**: On the death of Chola King Kulamurrathu Thunjiya Killivalavan, the poet addresses the potter: *\"O Kalam-Sey-Kooce, potter of wide clay earth! Can you fashion an urn wide enough to inter this great king whose fame filled the four directions? You must make your wheel the vast world, and Mount Meru your lump of clay!\"*\n- **Purananuru 256**: A grief-stricken mother requests the potter to mold a dual urn capable of holding both her fallen warrior son and herself, documenting the universal rite of Megalithic secondary urn entombment (*Mudhumakkal Thaazhi*)."
    },
    {
        "slug": "concept-clay-mineralogy-levigation-tempering-and-plasticity-kinetics",
        "category": "concept",
        "file": "concept-clay-mineralogy-levigation-tempering-and-plasticity-kinetics.md",
        "name_en": "Alluvial Clay Mineralogy, Water Levigation, Sand Tempering & Plasticity Kinetics",
        "name_ta": "வண்டல்மண் கனிமவியல், நீர்ப் படிவாக்கம், மணல் கலப்பு மற்றும் நெகிழ்வுத்தன்மை இயக்கவியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -1000,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Physicochemical properties of Tamil riverine clays (kaolinite, illite, montmorillonite): sediment levigation in decantation tanks, quartz sand/chaff tempering to reduce firing shrinkage, and optimal water-content plasticity curves.",
        "summary_ta": "தமிழக ஆற்றுப்படுகை வண்டல் களிமண்ணின் வேதியியல் இயற்பியல் பண்புகள்: படிவாக்கத் தொட்டிகளில் துகள்கள் பிரிப்பு, சுருங்குதலைத் தடுக்க குவார்ட்ஸ் மணல் கலத்தல் மற்றும் நெகிழ்வுத்தன்மை.",
        "sources": [
            "Archaeometry Ceramic Studies",
            "Geological Survey of India: Clay Mineralogy",
            "Tamil Nadu Ceramic Science Memoirs"
        ],
        "content": "# Alluvial Clay Mineralogy & Levigation Kinetics\n\nThe exceptional strength and thin-walled refinement of ancient Tamil pottery relied on systematic clay preparation protocols:\n\n**Sedimentary Processing:**\n- **Mineral Composition**: Clays harvested from river deltas (Thamirabarani, Kaveri, Vaigai) consist of mixed-layer illite-smectite and kaolinite, possessing high cation exchange capacity ($20-40\\\\text{ meq}/100\\\\text{g}$) and fine particle diameter (<2 microns).\n- **Levigation Cascades**: Raw clay was mixed with water in stepped settling basins. Heavy coarse fractions (gravel, iron concretions) settled first, allowing suspension of pure micro-fine clay slurry into drying pans.\n- **Controlled Tempering**: Potters incorporated 15–20% sub-angular quartz sand and sieved paddy husk ash (*umikkari*), preventing anisotropic shrinkage and thermal-shock spalling during open-kiln firing."
    },
    {
        "slug": "technology-inverted-firing-dual-atmosphere-pyrotechnics-black-and-red-ware",
        "category": "technology",
        "file": "technology-inverted-firing-dual-atmosphere-pyrotechnics-black-and-red-ware.md",
        "name_en": "Inverted Firing Reduction-Oxidation Pyrotechnics for Black-and-Red Ware (BRW)",
        "name_ta": "கவிழ்த்துச் சுடும் இருவகை காற்றுச் சுழல் சூளை எரிப்பு மற்றும் கருப்பு-சிவப்பு மண்பாண்ட நுட்பம்",
        "era": "Iron Age to Early Historic",
        "year_start": -1200,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "The sophisticated pyrotechnological mechanism producing Megalithic Black-and-Red Ware: placing vessels inverted over combustible organic fuel in the kiln, causing internal smoky carbon reduction (black) and external exposed oxidation (red).",
        "summary_ta": "கருப்பு-சிவப்பு மண்பாண்டங்களை உருவாக்கும் தனித்துவமான சூளை நுட்பம்: பாண்டங்களைக் கவிழ்த்து வைத்து எரிப்பதால் உள்ளே கார்பன் ஒடுக்கமும் (கருப்பு), வெளியே பிராணவாயு ஏற்பும் (சிவப்பு) ஏற்படும் இயற்பியல்.",
        "sources": [
            "Journal of Archaeological Science: BRW Pyrotechnology",
            "Archaeological Survey of India Technical Reports",
            "Adichanallur Ceramic Metallurgy"
        ],
        "content": "# Inverted Firing Reduction-Oxidation Pyrotechnics\n\nMegalithic Black-and-Red Ware (BRW) is the diagnostic ceramic fossil of South Indian Iron Age and Early Historic civilizational horizons:\n\n**Dual-Atmosphere Mechanism:**\n1. **Kiln Loading**: Pots were placed rim-downwards (inverted) directly over beds of organic fuel (cow dung, chaff, rice husks) inside pit kilns (*soozhai*).\n2. **Reducing Internal Atmosphere**: As the fuel slowly carbonized in oxygen-depleted cavities beneath the vessel, dense hydrocarbon smoke penetrated the interior porous clay walls. Iron oxides ($\\\\text{Fe}_2\\\\text{O}_3$) reduced into black magnetite ($\\\\text{Fe}_3\\\\text{O}_4$) and carbon soot became trapped inside the crystal lattices, producing a deep lustrous black finish.\n3. **Oxidizing External Atmosphere**: The upper outer walls remained exposed to circulating oxygen above $700^\\\\circ\\\\text{C}$, maintaining iron in its ferric state ($\\\\text{Fe}^{3+}$) to yield a vibrant terracotta red or slip burnished orange hue."
    },
    {
        "slug": "artifact-mudhumakkal-thaazhi-giant-urn-burials-and-black-and-red-ware-pots",
        "category": "artifact",
        "file": "artifact-mudhumakkal-thaazhi-giant-urn-burials-and-black-and-red-ware-pots.md",
        "name_en": "Mudhumakkal Thaazhi Giant Burial Urns, Ring Stands & Graffiti-Inscribed BRW",
        "name_ta": "முதுமக்கள் தாழி பெரும் ஈமப் பானைகள், மட்கலத் தாங்கிகள் மற்றும் குறியீட்டு கருப்பு-சிவப்பு பாண்டங்கள்",
        "era": "Iron Age to Sangam Era",
        "year_start": -1000,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "The material corpus of ancient Tamil funerary ceramics: colossal coiled burial urns (up to 1.5 meters height) with thumb-impressed applique bands, conical lids, wheel-turned ring stands, and post-firing Tamil-Brahmi/graffiti etched vessels.",
        "summary_ta": "பண்டைய தமிழகத்தின் ஈம மண்பாண்டத் தொகுப்பு: 1.5 மீட்டர் உயரம் கொண்ட பெரும் முதுமக்கள் தாழிகள், மட்கலத் தாங்கிகள், வட்ட மூடிகளும் தமிழ்ப் பிராமி மற்றும் கீறல் குறியீடுகள் கொண்ட பாண்டங்கள்.",
        "sources": [
            "Adichanallur Urn Burial Reports",
            "Keezhadi Archaeological Excavation Reports",
            "Tamil Nadu State Archaeology Department"
        ],
        "content": "# Mudhumakkal Thaazhi Burial Urns & Inscribed Ceramics\n\nFunerary ceramics uncovered at Adichanallur, Sanur, Keezhadi, and Kodumanal demonstrate unprecedented scale and ceramic durability:\n\n**Ceramic Features:**\n- **Monumental Urns (*Thaazhi*)**: Heavy coarse-red ware containers standing between 1.0 and 1.8 meters, manufactured via segmented coiling and paddle-thinning to withstand massive lithic earth pressures.\n- **Funerary Offerings**: Urns contained secondary skeletal remains accompanied by delicate miniature Black-and-Red Ware bowls, carnelian beads, iron daggers, and bronze vessels.\n- **Graffiti & Tamil-Brahmi Scripts**: Over 1,000 distinct post-firing graffiti symbols (ladders, suns, bows, hills) and early Tamil-Brahmi personal names were etched onto the burnished surfaces."
    },
    {
        "slug": "concept-kiln-thermal-gradient-thermodynamics-and-hematite-reduction",
        "category": "concept",
        "file": "concept-kiln-thermal-gradient-thermodynamics-and-hematite-reduction.md",
        "name_en": "Kiln Thermal Gradient Thermodynamics, Sintering Kinetics & Hematite Reduction",
        "name_ta": "சூளை வெப்ப சாய்வு இயக்கவியல், களிமண் உருகுநிலை மற்றும் ஹேமடைட் ஒடுக்க வேதியியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -1000,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "High-temperature chemical physics of Tamil ceramic kilns: thermal profiles reaching 650°C to 850°C, vitreous silicate sintering, hematite-to-magnetite reduction equilibria, and slip vitrification under charcoal fuel.",
        "summary_ta": "பண்டைய சூளைகளில் 650°C முதல் 850°C வரையிலான வெப்ப சாய்வு மற்றும் சிலிகேட் உருகுநிலை: ஹேமடைட் இரும்புத் தாது மேக்னடைட்டாக மாறும் வேதியியல் சமநிலை.",
        "sources": [
            "Ceramics International Journal",
            "Archaeological Metallurgy and Pyrotechnology",
            "Indian Journal of History of Science"
        ],
        "content": "# Kiln Thermal Gradient Thermodynamics & Hematite Reduction\n\nThe chemical transformation of raw earthen clay into hard, impervious Black-and-Red Ware depends on exact thermal management:\n\n**Reaction Kinetics ($650^\\\\circ\\\\text{C}-850^\\\\circ\\\\text{C}$):**\n- **Dehydroxylation**: Chemically bound hydroxyl groups within kaolinite ($\\\\text{Al}_2\\\\text{Si}_2\\\\text{O}_5(\\\\text{OH})_4$) dissociate between $450^\\\\circ\\\\text{C}$ and $600^\\\\circ\\\\text{C}$, collapsing the crystal lattice into amorphous metakaolin.\n- **Reduction Equilibrium**: In the localized reducing micro-climate of the inverted vessel interior:\n  $$\\\\text{Fe}_2\\\\text{O}_3 + \\\\text{CO} \\\\rightarrow 2\\\\text{Fe}_3\\\\text{O}_4 + \\\\text{CO}_2$$\n  This locks deep refractory black pigmentation into the inner wall.\n- **Slip Burnishing**: Application of fine iron-rich liquid clay slip followed by pebble burnishing aligns clay platelets parallel to the vessel surface, creating a mirror-like vitreous luster upon cooling."
    },
    {
        "slug": "institution-kalam-sey-kooce-corporation-of-hereditary-potters-and-kiln-masters",
        "category": "institution",
        "file": "institution-kalam-sey-kooce-corporation-of-hereditary-potters-and-kiln-masters.md",
        "name_en": "Kalam-Sey-Kooce Corporation: Hereditary Potters, Tile Makers & Kiln Masters",
        "name_ta": "கலம்செய்கோவே சங்கம்: மரபுவழிக் குயவர்கள், ஓடு செய்வோர் மற்றும் சூளைத் தலைவர்கள் சபை",
        "era": "Iron Age to Vijayanagara Era",
        "year_start": -500,
        "year_end": 1600,
        "thinai": "marutham",
        "summary_en": "The institutional organization of Tamil potters (Kuyavar / Velar): hereditary guilds managing village clay commons, collective communal kilns, funerary urn commissions, and temple terracotta sculpture.",
        "summary_ta": "பண்டைய தமிழ்க் குயவர் மற்றும் வேளார் கைவினைஞர்களின் சமூக அமைப்பு: களிமண் குளங்களின் பயன்பாட்டு உரிமை, பொதுச் சூளைகள் மேலாண்மை, ஈமத்தாழி தயாரிப்பு மற்றும் சுடுமண் சிற்பக் கலை.",
        "sources": [
            "South Indian Inscriptions: Potter Guild Charters",
            "Castes and Tribes of Southern India",
            "Sangam Institutional Anthropology"
        ],
        "content": "# Kalam-Sey-Kooce Corporation: Hereditary Potters\n\nCeramic production in ancient Tamil society occupied a pivotal intersection of agrarian utility, sacred ritual, and funerary engineering:\n\n**Corporate Guild Responsibilities:**\n- **Clay Rights (*Kalam-Patti*)**: Inscriptional records grant potters tax-free communal rights to mine tank beds (*eri-padugai*) for high-plasticity clay and firewood reserves.\n- **Funerary Obligations**: Master potters were commissioned by village elders to throw monumental urns (*Mudhumakkal Thaazhi*) for royal and civilian burials.\n- **Temple Terracotta (*Kuthirai & Ayyanar*)**: Created colossal votive terracotta guardian horses and protective deities fired in specialized open bonfires."
    },
    {
        "slug": "technology-fast-wheel-throwing-paddle-and-anvil-wall-thinning",
        "category": "technology",
        "file": "technology-fast-wheel-throwing-paddle-and-anvil-wall-thinning.md",
        "name_en": "Fast-Wheel Throwing, Paddle-and-Anvil Wall Thinning & Surface Burnishing",
        "name_ta": "வேகமான மண்பாண்டச் சக்கர சுழற்சி, தட்டுக்கல்-ஆழி கொண்டு சுவர்ப்பகுதி மெலிதாக்குதல் மற்றும் தேய்த்தல்",
        "era": "Iron Age to Modern Era",
        "year_start": -800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The mechanical shaping sequence of classical Tamil ceramics: heavy stone flywheel throwing, paddle-and-anvil (thattu-kal and aazhi) wall thinning and compaction, and hematite slip pebble burnishing.",
        "summary_ta": "பாரம்பரிய மண்பாண்ட உருவாக்கும் இயந்திரவியல் முறை: கனமான கருங்கல் சக்கர சுழற்சி, மரத்தட்டுப் பலகை மற்றும் சுடுமண் ஆழி கொண்டு அடித்து சுவரை மெலிதாக்கும் நுட்பம்.",
        "sources": [
            "Ethnoarchaeology of South Indian Pottery",
            "Ceramic Ethnotechnology Reports",
            "Archaeological Survey of India"
        ],
        "content": "# Fast-Wheel Throwing & Paddle-and-Anvil Wall Thinning\n\nThe formation of thin, resonance-capable ceramic vessels combined centrifugal wheel momentum with percussion thinning:\n\n**Forming Sequence:**\n1. **Flywheel Throwing**: A thick-walled cylinder with open base is raised on a low, heavy wooden or stone pivot wheel (*thigiri*) spun by a bamboo stick.\n2. **Paddle & Anvil Beating (*Thattu-Kal & Aazhi*)**: After partial drying (leather-hard stage), the potter inserts a spherical terracotta or stone anvil (*aazhi*) inside the vessel and rhythmically beats the exterior with a grooved wooden paddle (*thattu-kal*). This closes the base, expands internal volume by 40%, and aligns clay crystals to maximize tensile strength.\n3. **Slip Burnishing**: Liquid red ochre (*kaavi*) is wiped on the leather-hard exterior and vigorously rubbed with oily river agates or string seeds, compacting the surface to an impermeable seal."
    },
    {
        "slug": "place-adichanallur-ancient-pandya-urn-burial-pottery-haven",
        "category": "place",
        "file": "place-adichanallur-ancient-pandya-urn-burial-pottery-haven.md",
        "name_en": "Adichanallur: Ancient Pandyan Urn Burial Pottery Haven, Thamirabarani Megalithic Necropolis",
        "name_ta": "ஆதிச்சநல்லூர் - பண்டைய பாண்டியர் ஈமத்தாழி தளம், தாமிரபரணி பெருங்கற்கால மண்பாண்டப் பெருநகரம்",
        "era": "Iron Age to Sangam Era",
        "year_start": -1200,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "World-famous Megalithic burial site on the Thamirabarani River in Thoothukudi district, spanning 114 acres of high-density urn burials, yielding hundreds of pristine Black-and-Red Ware vessels, bronze artifacts, and gold diadems.",
        "summary_ta": "தூத்துக்குடி மாவட்டத்தில் தாமிரபரணி ஆற்றங்கரையில் 114 ஏக்கர் பரப்பளவில் அமைந்துள்ள வரலாற்றுச் சிறப்புமிக்க பெருங்கற்கால ஈமக்காடு: நூற்றுக்கணக்கான முதுமக்கள் தாழிகள் மற்றும் கருப்பு-சிவப்பு மண்பாண்டங்களின் தாயகம்.",
        "sources": [
            "ASI Adichanallur Excavation Reports",
            "Alexander Rea's 1902 Excavation Memoirs",
            "Carbon Dating Reports of Adichanallur"
        ],
        "content": "# Adichanallur: Ancient Urn Burial Pottery Haven\n\nAdichanallur represents the largest and most extensively researched Megalithic necropolis on the Indian subcontinent:\n\n**Archaeological Significance:**\n- Covering a barren quartz-gravel hillock overlooking the fertile Thamirabarani valley, excavations since 1876 have uncovered thousands of interlocking burial urns buried in deep bedrock pits.\n- Radiocarbon accelerator mass spectrometry (AMS) dates the earliest Adichanallur cultural horizons to between 1000 BCE and 600 BCE, confirming early sophistication in Black-and-Red Ware pottery.\n- The site demonstrates that specialized potting communities sustained massive production of ritual, domestic, and funerary vessels across generations."
    },
    {
        "slug": "concept-post-firing-graffiti-marks-tamil-brahmi-epigraphy-on-ceramics",
        "category": "concept",
        "file": "concept-post-firing-graffiti-marks-tamil-brahmi-epigraphy-on-ceramics.md",
        "name_en": "Post-Firing Ceramic Graffiti Marks, Tamil-Brahmi Transition & Ownership Scribing",
        "name_ta": "சுட்டபின் கீறப்பட்ட மண்பாண்டக் குறியீடுகள், தமிழ்ப் பிராமி எழுத்து வளர்ச்சி மற்றும் உரிமைப் பொறிப்புகள்",
        "era": "Iron Age to Sangam Era",
        "year_start": -800,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "The historical and semiotic evolution of post-firing pot-marks: pre-alphabetic geometric graffiti (triangles, ladders, cross-hatching) transitioning into the earliest Tamil-Brahmi scripts etched on Black-and-Red Ware rims.",
        "summary_ta": "மண்பாண்டங்களின் மீது சுட்டபின் கூரிய இரும்புக் கம்பி கொண்டு கீறப்பட்ட குறியீடுகளின் பரிணாமம்: பெருங்கற்கால வடிவங்கள் முதல் தமிழ்ப் பிராமி எழுத்துப் பொறிப்புகள் வரை.",
        "sources": [
            "Keezhadi Inscribed Potsherd Monographs",
            "Kodumanal Graffiti Corpus Reports",
            "Epigraphia Tamilica"
        ],
        "content": "# Post-Firing Graffiti Marks & Tamil-Brahmi Transition\n\nExcavated ceramics across Tamil Nadu provide conclusive epigraphical evidence for the democratization of literacy in early antiquity:\n\n**Semiotic Evolution:**\n- **Megalithic Graffiti (Pre-500 BCE)**: Geometrical symbols etched after firing using iron awls, functioning as clan insignias, potter marks, or astronomical markers.\n- **Tamil-Brahmi Emergence (Post-600 BCE)**: At Keezhadi, Kodumanal, and Porunthal, potsherds feature early Tamil-Brahmi script spelling out personal names (*Aadhan*, *Nedunjeliyan*, *Kuviran*), etched into the burnished slips of Black-and-Red bowls.\n- **Functional Context**: Literacy extended beyond royal stelae to everyday utilitarian ceramics owned by merchants, farmers, and weavers."
    },
    {
        "slug": "artifact-perforated-colanders-spouted-jars-and-terracotta-figurines",
        "category": "artifact",
        "file": "artifact-perforated-colanders-spouted-jars-and-terracotta-figurines.md",
        "name_en": "Perforated Ceramic Colanders, Spouted Ritual Jars & Terracotta Figurines",
        "name_ta": "துளைகளுள்ள மட்கல வடிகட்டிகள், மூக்குடை பாண்டங்கள் மற்றும் சுடுமண் சிற்பங்கள்",
        "era": "Iron Age to Sangam Era",
        "year_start": -600,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Specialized ceramic forms of the Sangam era: perforated vessels for aromatic steam filtration and rice gruel draining, narrow-spouted ritual libation jars, and hand-modeled anthropomorphic figurines.",
        "summary_ta": "சங்க கால சிறப்பு மண்பாண்ட வகைகள்: உணவு வடிக்கும் துளை வடிகலங்கள், நீர் ஊற்றும் மூக்குடைய ஜாடிகள் மற்றும் சுடுமண் மாந்தர் சிற்பங்கள்.",
        "sources": [
            "Keezhadi Archaeological Excavation Reports",
            "Kaveripoompattinam Ceramic Catalog",
            "Bulletin of the Madras Government Museum"
        ],
        "content": "# Perforated Colanders, Spouted Jars & Terracotta Figurines\n\nBeyond standard storage and funerary containers, Tamil potters created an elaborate range of functionally differentiated ceramic ware:\n\n**Diagnostic Types:**\n- **Perforated Colanders (*Ari-Paanai*)**: Vessels punctured with hundreds of uniform 3-5 mm holes across their hemispherical bases before firing, used for straining fermented toddy, boiling medicinal decoctions, and steaming rice.\n- **Spouted Libation Jars (*Mookku Paanai*)**: Elegant globular vessels equipped with curved tubular pouring spouts, utilized in household ritual ablutions and temple consecrations.\n- **Terracotta Sculptures**: Solid and hollow figurines depicting ear-ornamented women, caparisoned horses, and humped bulls, burnished and fired under both oxidizing and reducing flames."
    }
]

EDGES = [
    [
        "text-purananuru-verses-addressing-the-potter-kalam-sey-kooce",
        "celebrates",
        "institution-kalam-sey-kooce-corporation-of-hereditary-potters-and-kiln-masters",
        "material_culture",
        "Sangam Era",
        "Purananuru verses praise the skill and sacred funerary duties of the master potter guilds.",
        "Purananuru 228 & 256"
    ],
    [
        "concept-clay-mineralogy-levigation-tempering-and-plasticity-kinetics",
        "enables",
        "technology-fast-wheel-throwing-paddle-and-anvil-wall-thinning",
        "material_culture",
        "Iron Age to Modern Era",
        "Levigated illite-kaolinite clay with quartz temper provides ideal plasticity for flywheel raising and paddle beating.",
        "Archaeometry Studies"
    ],
    [
        "technology-fast-wheel-throwing-paddle-and-anvil-wall-thinning",
        "shapes",
        "artifact-mudhumakkal-thaazhi-giant-urn-burials-and-black-and-red-ware-pots",
        "material_culture",
        "Iron Age to Sangam Era",
        "Wheel throwing and percussion paddle-and-anvil wall compaction produce colossal burial urns and fine bowls.",
        "Ethnoarchaeology Reports"
    ],
    [
        "technology-inverted-firing-dual-atmosphere-pyrotechnics-black-and-red-ware",
        "fires",
        "artifact-mudhumakkal-thaazhi-giant-urn-burials-and-black-and-red-ware-pots",
        "material_culture",
        "Iron Age to Early Historic",
        "Inverted pit-kiln firing creates the characteristic dual-tone Black-and-Red Ware burial pottery.",
        "Archaeological Science"
    ],
    [
        "concept-kiln-thermal-gradient-thermodynamics-and-hematite-reduction",
        "underpins",
        "technology-inverted-firing-dual-atmosphere-pyrotechnics-black-and-red-ware",
        "material_culture",
        "Iron Age to Modern Era",
        "Thermal gradient and carbon monoxide atmosphere govern internal hematite reduction to black magnetite.",
        "Ceramics International"
    ],
    [
        "place-adichanallur-ancient-pandya-urn-burial-pottery-haven",
        "contains",
        "artifact-mudhumakkal-thaazhi-giant-urn-burials-and-black-and-red-ware-pots",
        "material_culture",
        "Iron Age to Sangam Era",
        "Adichanallur necropolis holds thousands of pristine burial urns and fine Black-and-Red vessels.",
        "ASI Adichanallur Reports"
    ],
    [
        "institution-kalam-sey-kooce-corporation-of-hereditary-potters-and-kiln-masters",
        "operates_in",
        "place-adichanallur-ancient-pandya-urn-burial-pottery-haven",
        "material_culture",
        "Iron Age to Vijayanagara Era",
        "Potters guilds maintained continuous ceramic production centers supplying the vast Thamirabarani burial ground.",
        "Rea 1902 Memoirs"
    ],
    [
        "concept-post-firing-graffiti-marks-tamil-brahmi-epigraphy-on-ceramics",
        "inscribes",
        "artifact-mudhumakkal-thaazhi-giant-urn-burials-and-black-and-red-ware-pots",
        "material_culture",
        "Iron Age to Sangam Era",
        "Potsherds carry etched post-firing Megalithic symbols and early Tamil-Brahmi ownership inscriptions.",
        "Keezhadi Inscribed Sherds"
    ],
    [
        "technology-fast-wheel-throwing-paddle-and-anvil-wall-thinning",
        "produces",
        "artifact-perforated-colanders-spouted-jars-and-terracotta-figurines",
        "material_culture",
        "Iron Age to Sangam Era",
        "Fast-wheel throwing produces perforated strainers, spouted jars, and votive terracotta art.",
        "Keezhadi Excavations"
    ],
    [
        "text-purananuru-verses-addressing-the-potter-kalam-sey-kooce",
        "documents",
        "place-adichanallur-ancient-pandya-urn-burial-pottery-haven",
        "material_culture",
        "Sangam Era",
        "Sangam elegies on burial urns match the real-world archaeological findings at Adichanallur.",
        "Purananuru 228"
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
    total_chunks = 0
    for d in DOSSIERS:
        slug = d["slug"]
        shelf = f"shelf-{d['category']}s"
        source_ref = f"knowledge/{category_dir(d['category'])}/{d['file']}"

        # Re-running must not duplicate chunks for a node.
        cur.execute("DELETE FROM rag_chunks WHERE node_slug = %s;", (slug,))

        chunks = [
            {
                "language": "en",
                "title": d["name_en"],
                "content": f"{d['name_en']}\n\nSummary:\n{d['summary_en']}\n\nKey Concepts:\n{d['content'][:1500]}",
            },
            {
                "language": "ta",
                "title": d["name_ta"],
                "content": f"{d['name_ta']}\n\nசுருக்கம்:\n{d['summary_ta']}\n\nமுக்கிய நுட்பங்கள்:\n{d['content'][:1500]}",
            },
        ]
        for ch in chunks:
            emb = get_embedding(ch["content"])
            emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            cur.execute("""
                INSERT INTO rag_chunks (node_slug, shelf, language, title, content, source_ref, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (slug, shelf, ch["language"], ch["title"], ch["content"], source_ref, emb_str))
            total_chunks += 1
        print(f"Embedded 2 chunks for: {slug}")
    conn.commit()
    print(f"Total chunks embedded: {total_chunks}")

    cur.close()
    conn.close()
    print("=== Harvester Complete! ===")

if __name__ == "__main__":
    main()
