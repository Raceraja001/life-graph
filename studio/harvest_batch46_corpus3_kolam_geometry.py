#!/usr/bin/env python3
"""
Harvester: Batch 46 - Ancient Tamil Kolam Threshold Geometry, Pulli-Sikku Eulerian Graph Topology & Rice-Flour Ecology
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
        "slug": "text-nachiyar-tirumozhi-and-classical-tamil-references-to-mezhukkidu-and-threshold-kolam",
        "category": "text",
        "file": "text-nachiyar-tirumozhi-and-classical-tamil-references-to-mezhukkidu-and-threshold-kolam.md",
        "name_en": "Nachiyar Tirumozhi & Classical Tamil Poetic References to Mezhukkidu and Threshold Kolam",
        "name_ta": "நாச்சியார் திருமொழி மற்றும் செவ்வியல் தமிழ் இலக்கியங்களில் மெழுக்கிடுதல், வாசல் கோல மரபு",
        "era": "Sangam to Bhakti Era",
        "year_start": -300,
        "year_end": 900,
        "thinai": "marutham",
        "summary_en": "Classical Tamil literary attestations in Purananuru, Narrinai, Kalithogai, and Andal's Nachiyar Tirumozhi and Tiruppavai describing threshold sweeping, cow-dung plastering (mezhukkidu), white rice-flour floor diagrams (kolam / vari), and auspicious body/ground ornamentation (thoyyil).",
        "summary_ta": "புறநானூறு, நற்றிணை, கலித்தொகை மற்றும் ஆண்டாளின் நாச்சியார் திருமொழி, திருப்பாவையில் குறிப்பிடப்படும் முற்றம் பெருக்குதல், சாணம் மெழுக்கிடுதல், வெண்மாவுக் கோலம் மற்றும் தொய்யில் ஓவியக் குறிப்புகள்.",
        "sources": [
            "Andal Nachiyar Tirumozhi",
            "Andal Tiruppavai",
            "Purananuru",
            "Kalithogai",
            "Narrinai"
        ],
        "content": "# Nachiyar Tirumozhi & Classical Tamil References to Threshold Kolam\n\nClassical Tamil Sangam anthologies and Bhakti hymns preserve foundational literary attestations of ritual floor preparation (*mezhukkidu*) and geometric threshold drawing (*kolam*):\n\n**Literary Attestations:**\n- **Sangam Threshold Cleansing & Thoyyil**: *Purananuru* and *Narrinai* describe domestic courtyards (*murram*) swept clean with grass brooms and smoothed with cow-dung emulsion (*mezhugu*), while *Kalithogai* and *Ainkurunuru* celebrate symmetrical foliate and curvilinear motifs (*thoyyil* and *vari*) traced with sandal paste and white rice flour.\n- **Andal's Nachiyar Tirumozhi & Tiruppavai**: In *Nachiyar Tirumozhi* (First Decade, *Tai-Neeradal*), Andal describes young women in the month of *Margazhi* sweeping the street threshold, smearing fresh cow-dung slurry (*mezhukkidu*), scattering fine white sand and rice flour (*ven-manal*), and drawing auspicious geometric mandalas to invoke seasonal rains and fertility."
    },
    {
        "slug": "concept-sikku-kolam-pulli-grid-eulerian-graph-topology-and-braid-theory",
        "category": "concept",
        "file": "concept-sikku-kolam-pulli-grid-eulerian-graph-topology-and-braid-theory.md",
        "name_en": "Sikku-Kolam (Neli-Kolam) Pulli Dot-Matrix Eulerian Graph Topology & Knot Weaving",
        "name_ta": "சிக்குக் கோலம் (நெளிக்கோலம்) புள்ளி வலைப்பின்னல் ஆய்லர் வரைபடக் கோட்பாடும் முடிச்சு இடவியலும்",
        "era": "Ancient to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Topological graph theory of Tamil Sikku-Kolam (Neli-Kolam / Kambi-Kolam): tracing continuous closed Eulerian circuits around orthogonal (ner-pulli) or rhombic interlaced (idukku-pulli) dot matrices without lifting the fingers, forming 4-regular planar projection graphs and alternating braid crossings.",
        "summary_ta": "சிக்குக் கோலம் எனப்படும் நெளிக்கோலத்தின் கணித வரைபடக் கோட்பாடு: நேர்ப் புள்ளி மற்றும் இடுக்குப் புள்ளி வரிசைகளைச் சுற்றி விரல் எடுக்காமல் வரையப்படும் மூடிய ஆய்லர் சுழல் பாதைகள் (Eulerian loops).",
        "sources": [
            "Marcia Ascher Ethnomathematics: Sikku Kolam",
            "Gift Siromoney Kolam Array Grammars",
            "Topological Graph Theory of South Indian Threshold Diagrams"
        ],
        "content": "# Sikku-Kolam Pulli-Grid Eulerian Graph Topology\n\nThe *Sikku-Kolam* (also called *Neli-Kolam* or *Kambi-Kolam*) is a rigorous topological discipline in which curved lines orbit a discrete lattice of dots (*pulli*) without ever intersecting a dot or leaving a loose line-end:\n\n**Graph-Theoretic Properties:**\n- **Pulli Lattice Dualism**: Artists lay down either an orthogonal square grid (*ner-pulli*, $(m \\times n)$) or a staggered rhombic/hexagonal grid (*idukku-pulli* or *oodu-pulli*, e.g., $1-3-5-7-5-3-1$). Each *pulli* acts as a topological obstacle around which the continuous line must loop.\n- **4-Regular Planar Eulerian Circuits**: Because every curve segment entering a crossing region between two adjacent dots exits transversely, the resulting diagram is a 4-regular planar graph ($deg(v) = 4$ at every vertex). A classical *Sikku-Kolam* ideally forms a single unicursal Eulerian tour (one continuous closed loop visiting every inter-dot vertex twice) executed in one unbroken sweep."
    },
    {
        "slug": "concept-dihedral-symmetry-groups-fractal-self-similarity-and-ethnomathematical-array-grammars",
        "category": "concept",
        "file": "concept-dihedral-symmetry-groups-fractal-self-similarity-and-ethnomathematical-array-grammars.md",
        "name_en": "Dihedral Symmetry Groups (D4, C4), Fractal Self-Similarity & Kolam Array Grammars",
        "name_ta": "கோலங்களின் இருமுகச் சமச்சீர் குலங்கள் (D4, C4), பிராக்டல் சுய-ஒப்புமை மற்றும் அணி இலக்கணம்",
        "era": "Medieval to Modern Era",
        "year_start": 500,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Formal mathematical structure of Tamil Kolam patterns studied in ethnomathematics and theoretical computer science: dihedral ($D_4, D_6$) and cyclic ($C_4$) point symmetry groups, recursive L-system fractal space-filling curves (Anklet and Pavithram motifs), and two-dimensional context-free picture array grammars.",
        "summary_ta": "இனக்கணிதவியல் மற்றும் கணினி அறிவியலில் ஆராயப்படும் கோலங்களின் இருமுகச் சமச்சீர் (D4), சுழல் சமச்சீர் (C4), பிராக்டல் சுய-ஒப்புமை மற்றும் இருபரிமாண அணி இலக்கணக் கோட்பாடுகள்.",
        "sources": [
            "Gift Siromoney & Rani Siromoney Array Grammars (Madras Christian College)",
            "Przemyslaw Prusinkiewicz L-Systems and Kolam Fractals",
            "Gerdes & Ascher Ethnomathematics"
        ],
        "content": "# Dihedral Symmetry Groups, Fractals & Array Grammars\n\nStarting in the 1970s at Madras Christian College, mathematicians Gift Siromoney, Rani Siromoney, and K. Krithivasan demonstrated that traditional Tamil *Kolam* designs encode formal two-dimensional picture languages:\n\n**Mathematical Formalisms:**\n- **Dihedral & Rotational Point Groups**: Threshold patterns are systematically classified by their planar invariance under the dihedral group $D_4$ (four $90^\\circ$ rotations plus four mirror reflections across orthogonal and diagonal axes) or the chiral cyclic group $C_4$ (swastika-like *Pavithram* loops invariant under $90^\\circ$ rotation but lacking mirror reflection).\n- **Fractal Space-Filling Curves & L-Systems**: Classic expanding patterns such as the *Kolusu* (anklet) and *Naga-bandham* grow recursively across $(2^k - 1) \\times (2^k - 1)$ dot grids, converging in the limit to continuous Peano- and Sierpinski-like space-filling fractals generated by deterministic Lindenmayer systems (L-systems) and context-free array grammars."
    },
    {
        "slug": "concept-podi-kolam-rice-flour-bhuta-yajna-ecology-and-saanam-thelippu-microbial-hygiene",
        "category": "concept",
        "file": "concept-podi-kolam-rice-flour-bhuta-yajna-ecology-and-saanam-thelippu-microbial-hygiene.md",
        "name_en": "Podi-Kolam Rice-Flour Bhuta-Yajna Ecology & Saanam-Thelippu Threshold Hygiene",
        "name_ta": "பொடிக் கோல அரிசி மாவு ஜீவகாருண்யச் சூழலியலும் சாணம் தெளிப்பு நுண்ணுயிர் சுகாதாரமும்",
        "era": "Ancient to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Ecological and hygienic functions of the daily Tamil dawn threshold ritual: sprinkling diluted cow-dung slurry (saanam-thelippu) to bind dust, cool the earthen courtyard (vasal), and form a bacteriostatic crust, followed by drawing with dry coarse rice flour (podi-kolam / arisi-maa) as daily micro-charity (bhuta-yajna) feeding ants, sparrows, and soil fauna.",
        "summary_ta": "அதிகாலையில் வாசலில் சாணம் தெளித்துப் புழுதியை அடக்கி நுண்ணுயிர்களைக் கட்டுப்படுத்தும் சுகாதார முறையும், எறும்பு, குருவி உள்ளிட்ட சிற்றுயிர்களுக்கு உணவாகப் பச்சரிசி மாவில் பொடிக் கோலமிடும் ஜீவகாருண்யச் சூழலியலும்.",
        "sources": [
            "Vijaya Nagarajan Feeding a Thousand Souls: Women, Ritual, and Ecology in India",
            "Tamil Household Ethnobiology Studies",
            "Tirukkural & Traditional Domestic Dharmashastra"
        ],
        "content": "# Rice-Flour Bhuta-Yajna Ecology & Saanam-Thelippu Hygiene\n\nTraditional Tamil domestic ethics mandate that the daily dawn *Kolam* be drawn with coarse dry raw-rice flour (*pacharisi podi-kolam*) rather than inert white stone powder (*maavu-kallu*):\n\n**Ecological & Hygienic Functions:**\n- **Daily Micro-Charity (*Bhuta-Yajna* / *Jeeva-Karunyam*)**: Before the household lights its kitchen hearth, scattering nutrient-rich rice flour across the threshold provides a predictable daily foraging ground for harvester ants (*erumbu*), house sparrows (*oor-kuruvi*), palm squirrels (*anil*), beetles, and soil micro-arthropods—integrating urban and rural doorways into local trophic webs.\n- **Cow-Dung Slurry Sprinkling (*Saanam-Thelippu*)**: Sprinkling water mixed with fresh herbivorous cow dung over swept earth flocculates fine silicate dust through mucopolysaccharide binding, lowers surface temperature via evaporative cooling, and deposits beneficial *Bacillus* and *Pseudomonas* flora that suppress pathogenic molds."
    },
    {
        "slug": "technology-podi-kolam-thumb-index-pinch-kinematics-and-pulli-matrix-registration",
        "category": "technology",
        "file": "technology-podi-kolam-thumb-index-pinch-kinematics-and-pulli-matrix-registration.md",
        "name_en": "Podi-Kolam Thumb-Index Pinch-Release Kinematics & Freehand Pulli Matrix Registration",
        "name_ta": "பொடிக் கோல விரல் இடுக்கு மாவு உதிர்ப்பு நுட்பமும் நேர்-இடுக்குப் புள்ளி வரிசை அளவீடும்",
        "era": "Ancient to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Biomechanical drawing craft of dry coarse rice-flour Kolam (podi-kolam): holding a reservoir of flour in the cupped palm while shearing a steady stream between thumb and index finger (viral-idukku), bending from the hip with straight knees, and registering uniform ner-pulli and idukku-pulli grids by eye and finger-span.",
        "summary_ta": "உள்ளங்கையில் அரிசி மாவை ஏந்திப் பெருவிரல் மற்றும் ஆள்காட்டி விரல் இடுக்கின் வழியே சீரான கோடுகளாக உதிர்க்கும் உடலியல் நுட்பமும், முழங்கால் மடங்காமல் குனிந்து புள்ளிகளைத் துல்லியமாக வைக்கும் முறையும்.",
        "sources": [
            "Ethnography of South Indian Kolam Practitioners",
            "Lilananda & Nagarajan Kolam Craft Studies",
            "Traditional Tamil Domestic Arts Manuals"
        ],
        "content": "# Podi-Kolam Pinch-Release Kinematics & Pulli Registration\n\nDrawing crisp, uniform lines and curves with loose dry powder on damp earth requires refined digital motor control and postural discipline:\n\n**Biomechanical & Spatial Techniques:**\n- **Thumb-Index Shear Metering (*Viral-Idukku*)**: Coarse raw-rice flour (sieved to remove ultrafine sticky starch) is held in the hollow of the fingers while the thumb oscillates laterally against the first two phalanges of the index and middle fingers, metering out a continuous ribbon of constant width ($2-4\\text{ mm}$) or twin parallel lines (*irattai-izhai*).\n- **Freehand Pulli Registration & Posture**: Without rulers or chalk strings, the practitioner establishes the central spinal row of dots (*nadu-pulli*) using thumb-to-index span intervals, then populates the orthogonal (*ner-pulli*) or triangularly offset (*idukku-pulli*) array while bending deeply from the waist (`uttanasana`-like posture) without resting knees on the wet floor."
    },
    {
        "slug": "technology-maa-kolam-wet-rice-paste-grinding-and-kaavi-red-ochre-border-framing",
        "category": "technology",
        "file": "technology-maa-kolam-wet-rice-paste-grinding-and-kaavi-red-ochre-border-framing.md",
        "name_en": "Maa-Kolam (Izhaik-Kolam) Wet Rice-Paste Grinding & Kaavi-Kodu Red Ochre Framing",
        "name_ta": "மாக்கோலம் (இழைக்கோலம்) பச்சரிசி விழுது அரைப்பு முறையும் செம்மண் காவிக்கோடு கட்டமைப்பும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Festive and auspicious threshold painting technology: wet stone-grinding soaked raw rice into a smooth colloidal batter (maa-kolam / izhaik-kolam) applied with a dipped cotton rag or three fingers for multi-day durability, bordered by vivid ferruginous red ochre bands (kaavi-kodu / seman) that visually anchor the white geometry.",
        "summary_ta": "பண்டிகை மற்றும் மங்கல நிகழ்வுகளுக்கு ஊறவைத்த பச்சரிசியை அம்மியில் நைசாக அரைத்துத் துணி அல்லது விரல்களால் இடும் மாக்கோல (இழைக்கோலம்) நுட்பமும், வெண்மையை எடுப்பாகக் காட்டும் செங்காவி (காவிக்கோடு) கரை அமைப்பும்.",
        "sources": [
            "South Indian Temple & Domestic Ritual Art Traditions",
            "Layard Labyrinth and Threshold Designs of Tamil Nadu",
            "Pigment and Colloidal Binding Studies in Folk Floor Art"
        ],
        "content": "# Maa-Kolam Wet Rice-Paste & Kaavi-Kodu Red Ochre Framing\n\nFor auspicious weddings, Fridays, *Pongal*, and temple festivals where threshold diagrams must endure foot traffic without blowing away, dry powder is replaced by wet colloidal suspension (*Maa-Kolam* or *Izhaik-Kolam*):\n\n**Formulation & Chromatic Framing:**\n- **Wet Colloidal Grinding**: Raw rice (*pacharisi*) soaked for two hours is ground on a granite mortar (*ammi* or *attu-kal*) with a pinch of slaked lime or fenugreek into a silky, thixotropic white slurry. A small cotton cloth pad (*thuni*) soaked in the batter is squeezed between the fingers so a continuous liquid stream flows down the index and middle fingertips to trace intricate *Padi-Kolam* (stepped altar) and *Hridaya-Kamalam* lotus mandalas.\n- **Kaavi-Kodu Red Ochre Borders**: Once the white amylopectin film dries bright matte white, its outer perimeter steps are outlined with broad bands of wet ferruginous red ochre clay (*kaavi-katti* or *seman*), creating stark red-and-white chromatic contrast and sealing the edges."
    },
    {
        "slug": "artifact-kolam-kuzhal-perforated-brass-stencil-rollers-and-sieve-tins",
        "category": "artifact",
        "file": "artifact-kolam-kuzhal-perforated-brass-stencil-rollers-and-sieve-tins.md",
        "name_en": "Kolam-Kuzhal Perforated Brass Stencil Rollers & Punched Thattu-Achchu Sieve Tins",
        "name_ta": "கோலக் குழல் துளையிட்ட பித்தளை உருளைகளும் தட்டு அச்சுச் சல்லடைக் கருவிகளும்",
        "era": "Late Medieval to Modern Era",
        "year_start": 1600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Mechanical sheet-metal implements crafted by Tamil braziers (Kanchar) for rapid street and corridor decoration: hollow cylindrical brass or tin rollers (kolam-kuzhal) pierced with floral and geometric dot matrices around an axle wire, and flat perforated stencil pans (thattu-achchu) tapped to transfer instant mandalas.",
        "summary_ta": "வீதி உலா மற்றும் நீண்ட தாழ்வாரங்களில் விரைவாகக் கோலமிடக் கன்னார் கலைஞர்களால் உருவாக்கப்பட்ட துளையிட்ட பித்தளைக் கோலக் குழல் உருளைகளும், தட்டு அச்சுச் சல்லடைக் கருவிகளும்.",
        "sources": [
            "Government Museum Chennai Metalware & Folk Art Collections",
            "DakshinaChitra Heritage Museum Domestic Implements Catalog",
            "Artisans of South India: Sheet-Metal Stencil Craft"
        ],
        "content": "# Kolam-Kuzhal Brass Stencil Rollers & Thattu-Achchu Tins\n\nTo lay continuous decorative borders (*Bara-Kolam*) along long temple processional streets and pillared corridors (*prakaram*), Tamil metalworkers devised precision perforated dispensers:\n\n**Instrument Mechanics:**\n- **Perforated Brass Roller Tubes (*Kolam-Kuzhal*)**: A hollow cylinder of sheet brass or tinned iron ($15-25\\text{ cm}$ long, $5\\text{ cm}$ diameter) is hand-punched from the inside out with repeating floral, creeper (*kodi*), or chariot-border patterns. Filled halfway with dry white powder through a hinged end-cap and mounted on a bent wire handle, the cylinder rolls across the ground, depositing a continuous periodic frieze via centrifugal and gravitational sifting.\n- **Flat Stencil Sieve Tins (*Thattu-Achchu*)**: Shallow circular tin dishes pierced with concentric lotus or star matrices are lightly tapped against the ground to stamp instant symmetric dot grids or finished floral medallions."
    },
    {
        "slug": "artifact-margazhi-poosani-poo-pumpkin-blossoms-and-saana-pillaiyar-threshold-cones",
        "category": "artifact",
        "file": "artifact-margazhi-poosani-poo-pumpkin-blossoms-and-saana-pillaiyar-threshold-cones.md",
        "name_en": "Margazhi Saana-Pillaiyar Cow-Dung Cones, Poosani-Poo Pumpkin Flowers & Bhogi Varatti",
        "name_ta": "மார்கழி சாணப் பிள்ளையார் கூம்புகள், பூசணிப் பூ அலங்காரம் மற்றும் போகி வரட்டிச் சடங்கு",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Seasonal ritual artifacts crowning the Tamil dawn Kolam throughout the solar month of Margazhi (December–January): hand-molded conical mounds of fresh cow dung (saana-pillaiyar / gobbara-pillaiyar) set in the center of the threshold mandala, topped with golden-yellow pumpkin blossoms (poosani-poo), and later dried into fuel cakes (varatti) for Pongal.",
        "summary_ta": "மார்கழி மாத அதிகாலைக் கோலத்தின் நடுவே வைக்கப்படும் சாணப் பிள்ளையார் கூம்புகள், அதன் மேல் சூட்டப்படும் மஞ்சள் பூசணிப் பூக்கள் மற்றும் தைப் பொங்கல் போகிக்குச் சேகரிக்கப்படும் வரட்டி மரபு.",
        "sources": [
            "Andal Nachiyar Tirumozhi Commentaries",
            "Festivals of Tamil Nadu: Margazhi and Pongal Ethnography",
            "Botanical Symbolism of Cucurbita maxima in South Indian Ritual"
        ],
        "content": "# Margazhi Saana-Pillaiyar Cones & Poosani-Poo Pumpkin Flowers\n\nThroughout the thirty dewy mornings of the solar month of *Margazhi* (mid-December to mid-January), the expansive threshold *Kolam* is crowned with a specific botanical and pastoral assemblage:\n\n**Material & Seasonal Cycle:**\n- **Saana-Pillaiyar & Poosani-Poo**: A small, fluted cone of fresh cow dung (*Saana-Pillaiyar* or *Gobbara-Pillaiyar*) is pressed by hand and placed at the geometric center (*bindu*) of the wet or dry rice-flour Kolam. Into its apex is inserted a freshly plucked, flared golden-yellow male blossom of the winter ash-gourd or yellow pumpkin (*Poosani-Poo*, *Cucurbita maxima*), accented with turmeric, kumkum, and *avaram* (*Senna auriculata*) petals.\n- **Solar Harvest Recycling**: At midday, when the flower wilts, each day's dung cone and blossom is collected, flattened onto sunny courtyard walls to dry into desiccated bio-fuel cakes (*varatti*), and burned in the purifying *Bhogi* dawn bonfire on the eve of the *Thai Pongal* harvest festival."
    },
    {
        "slug": "institution-matrilineal-threshold-pedagogy-kolam-pattern-notebooks-and-margazhi-street-guilds",
        "category": "institution",
        "file": "institution-matrilineal-threshold-pedagogy-kolam-pattern-notebooks-and-margazhi-street-guilds.md",
        "name_en": "Matrilineal Threshold Pedagogy, Kolam-Pusthakam Pattern Notebooks & Margazhi Street Collectives",
        "name_ta": "தாய்வழி வாசல் கோலப் பயிற்சி, கோலப் புத்தகக் கையேடுகள் மற்றும் மார்கழி வீதிக் குழுக்கள்",
        "era": "Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Social and pedagogical institutions sustaining Tamil geometric floor art: matrilineal dawn apprenticeship training girls from simple 3x3 ner-pulli loops to 21x21 labyrinthine Sikku-Kolams, heirloom graph-paper pattern notebooks (kolam-pusthakam) passed down in trousseaus, and cooperative neighborhood women's collectives during Margazhi.",
        "summary_ta": "தாயிடமிருந்து மகளுக்குக் கடத்தப்படும் அதிகாலைக் கோலப் பயிற்சி முறை, சீர்வரிசையாக அளிக்கப்படும் கையெழுத்துக் கோலப் புத்தகங்கள் மற்றும் மார்கழி மாதத்தில் வீதிப் பெண்கள் இணைந்து வரையும் கூட்டுக் கோல மரபு.",
        "sources": [
            "Vijaya Nagarajan Threshold Pedagogies in Tamil Nadu",
            "Archival Household Kolam Notebooks of Chettinad and Thanjavur",
            "Folklore and Women's Mathematical Traditions of South India"
        ],
        "content": "# Matrilineal Threshold Pedagogy & Kolam Pattern Notebooks\n\nFor centuries outside formal schooling, the Tamil household threshold functioned as an open-air academy of visual combinatorics, memory, and spatial reasoning transmitted through female lineages:\n\n**Pedagogical & Communal Institutions:**\n- **Progressive Pulli Apprenticeship**: Young girls begin by placing dot grids for their mothers and grandmothers, advancing from elementary $3 \\times 3$ and $5 \\times 5$ *ner-pulli* loops to complex $15 \\times 15$ and $21 \\times 21$ *idukku-pulli* *Sikku-Kolams* memorized through rhythmic numerical chants (e.g., *\"twenty-one dots to one, interlaced\"*).\n- **Heirloom Kolam Notebooks (*Kolam-Pusthakam*)**: Since the nineteenth century, women have compiled treasured hand-drawn dot-and-loop manuscripts on squared graph paper, gifted from mother to bride as part of her wedding trousseau (*seer-varisai*).\n- **Margazhi Street Collectives**: During *Margazhi* and temple car festivals (*ther-thiruvizha*), neighboring women coordinate across property lines to carpet entire streets with interlocking geometric runners ahead of the deity's procession."
    },
    {
        "slug": "place-mylapore-ancient-kapaleeswarar-agrahara-kolam-and-threshold-haven",
        "category": "place",
        "file": "place-mylapore-ancient-kapaleeswarar-agrahara-kolam-and-threshold-haven.md",
        "name_en": "Mylapore: Ancient Kapaleeswarar Mada-Veedhi & Tank-Street Margazhi Kolam Haven",
        "name_ta": "மயிலாப்பூர் - கபாலீஸ்வரர் மாடவீதிகள் மற்றும் சித்திரக்குளத் தெருக்களின் மார்கழிக் கோலத் தளம்",
        "era": "Pallava to Modern Era",
        "year_start": 600,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Historic coastal-estuarine temple quarter of Mylapore (Mayilappur, lat 13.0330, lng 80.2700) in Chennai surrounding the Kapaleeswarar Temple and Chitrakulam tank, celebrated for its four Mada Veedhis and traditional agrahara streets where complex Margazhi Sikku-Kolam and Padi-Kolam threshold geometry has flourished for centuries.",
        "summary_ta": "சென்னை மயிலாப்பூரில் (அட்சரேகை 13.0330, தீர்க்கரேகை 80.2700) கபாலீஸ்வரர் கோவில் மாடவீதிகள் மற்றும் சித்திரக்குளத் தெருக்களில் நூற்றாண்டுகளாகத் தழைத்தோங்கும் மார்கழிச் சிக்குக் கோலம் மற்றும் படிக்கோலப் பாரம்பரியத் தளம்.",
        "sources": [
            "Mylapore Kapaleeswarar Temple Epigraphy & History",
            "Madras Tercentenary Commemoration Volume",
            "Mylapore Festival & Margazhi Threshold Art Archives"
        ],
        "content": "# Mylapore: Kapaleeswarar Mada-Veedhi & Threshold Kolam Haven\n\nSituated at latitude $13.0330^\\circ\\text{ N}$, longitude $80.2700^\\circ\\text{ E}$ in the coastal *neithal* zone of Chennai, ancient Mylapore (*Mayilappur*, the Pallava port praised by Tirugnanasambandar and Peyalvar) is the premier living urban sanctuary of Tamil threshold *Kolam* geometry:\n\n**Urban & Cultural Landscape:**\n- **Mada-Veedhi & Tank-Street Corridors**: Around the sacred *Kapaleeswarar Temple* tank (*Theppakulam*) and *Chitrakulam* tank, the four broad *Mada Veedhis* and adjoining *Sannidhi* and *Agrahara* lanes preserve traditional verandahs (*thinnai*) and wide thresholds where households compete each *Margazhi* dawn to execute monumental $25\\text{-dot}$ to $51\\text{-dot}$ *Sikku-Kolams* and *Kaavi*-framed *Padi-Kolams*.\n- **Living Heritage Revival**: As dawn *Tiruppavai* and *Tiruvempavai* recitations echo along North Mada Street and Pitchu Pillai Street, master practitioners transform the neighborhood pavement into an open-air gallery of Eulerian knot topology and symmetrical rice-paste mandalas."
    }
]

EDGES = [
    [
        "text-nachiyar-tirumozhi-and-classical-tamil-references-to-mezhukkidu-and-threshold-kolam",
        "documents",
        "concept-podi-kolam-rice-flour-bhuta-yajna-ecology-and-saanam-thelippu-microbial-hygiene",
        "material_culture",
        "Sangam to Bhakti Era",
        "Classical Tamil poems and Andal's Nachiyar Tirumozhi document sweeping courtyards, cow-dung mezhukkidu, and dawn rice-flour threshold drawings.",
        "Nachiyar Tirumozhi & Purananuru"
    ],
    [
        "concept-sikku-kolam-pulli-grid-eulerian-graph-topology-and-braid-theory",
        "governs",
        "technology-podi-kolam-thumb-index-pinch-kinematics-and-pulli-matrix-registration",
        "material_culture",
        "Ancient to Modern Era",
        "Eulerian 4-regular planar loop topology governs how continuous curved lines weave around orthogonal and rhombic pulli dot matrices.",
        "Marcia Ascher Ethnomathematics"
    ],
    [
        "concept-dihedral-symmetry-groups-fractal-self-similarity-and-ethnomathematical-array-grammars",
        "formalizes",
        "concept-sikku-kolam-pulli-grid-eulerian-graph-topology-and-braid-theory",
        "material_culture",
        "Medieval to Modern Era",
        "Dihedral symmetry groups (D4, C4), L-system fractals, and Siromoney array grammars formalize the mathematical structure of Sikku-Kolam loops.",
        "Gift Siromoney Array Grammars"
    ],
    [
        "concept-podi-kolam-rice-flour-bhuta-yajna-ecology-and-saanam-thelippu-microbial-hygiene",
        "prepares",
        "technology-podi-kolam-thumb-index-pinch-kinematics-and-pulli-matrix-registration",
        "material_culture",
        "Ancient to Modern Era",
        "Cow-dung water sprinkling (saanam-thelippu) binds dust and prepares a damp, high-contrast surface for pinching dry rice-flour podi-kolam.",
        "Feeding a Thousand Souls"
    ],
    [
        "technology-podi-kolam-thumb-index-pinch-kinematics-and-pulli-matrix-registration",
        "complements",
        "technology-maa-kolam-wet-rice-paste-grinding-and-kaavi-red-ochre-border-framing",
        "material_culture",
        "Sangam to Modern Era",
        "Daily dry rice-flour pinch drawing (podi-kolam) is complemented on festivals and weddings by durable wet-ground rice batter (maa-kolam) framed with red ochre kaavi-kodu.",
        "South Indian Ritual Art Studies"
    ],
    [
        "technology-maa-kolam-wet-rice-paste-grinding-and-kaavi-red-ochre-border-framing",
        "pairs_with",
        "artifact-kolam-kuzhal-perforated-brass-stencil-rollers-and-sieve-tins",
        "material_culture",
        "Late Medieval to Modern Era",
        "Festive wet maa-kolam threshold mandalas are paired with perforated brass kolam-kuzhal rollers that lay continuous floral borders along processional streets.",
        "DakshinaChitra Domestic Catalog"
    ],
    [
        "technology-podi-kolam-thumb-index-pinch-kinematics-and-pulli-matrix-registration",
        "frames",
        "artifact-margazhi-poosani-poo-pumpkin-blossoms-and-saana-pillaiyar-threshold-cones",
        "material_culture",
        "Sangam to Modern Era",
        "Dawn Margazhi threshold kolams frame a central Saana-Pillaiyar cow-dung cone crowned with a golden-yellow poosani-poo pumpkin blossom.",
        "Festivals of Tamil Nadu"
    ],
    [
        "institution-matrilineal-threshold-pedagogy-kolam-pattern-notebooks-and-margazhi-street-guilds",
        "transmits",
        "concept-dihedral-symmetry-groups-fractal-self-similarity-and-ethnomathematical-array-grammars",
        "material_culture",
        "Medieval to Modern Era",
        "Matrilineal dawn apprenticeships and heirloom kolam-pusthakam graph notebooks transmit complex symmetrical and fractal pulli-kolam combinatorics across generations.",
        "Vijaya Nagarajan Threshold Pedagogies"
    ],
    [
        "place-mylapore-ancient-kapaleeswarar-agrahara-kolam-and-threshold-haven",
        "hosts",
        "institution-matrilineal-threshold-pedagogy-kolam-pattern-notebooks-and-margazhi-street-guilds",
        "material_culture",
        "Pallava to Modern Era",
        "The historic Mada Veedhis and tank streets around Mylapore Kapaleeswarar Temple host vibrant Margazhi women's street collectives and heritage Kolam competitions.",
        "Mylapore Festival Archives"
    ],
    [
        "text-nachiyar-tirumozhi-and-classical-tamil-references-to-mezhukkidu-and-threshold-kolam",
        "contextualizes",
        "artifact-margazhi-poosani-poo-pumpkin-blossoms-and-saana-pillaiyar-threshold-cones",
        "material_culture",
        "Sangam to Bhakti Era",
        "Andal's Margazhi hymns contextualize the dawn threshold preparation and seasonal floral offerings celebrated in Tamil winter harvest rituals.",
        "Andal Tiruppavai & Nachiyar Tirumozhi"
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
